"""
Deployment views for managing Vercel frontend deployments
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from tenant_schemas.utils import get_public_schema_name, schema_context

from .models import Tenant
from ecommerce_crm.services.vercel_deployment import deploy_tenant_frontend, VercelDeploymentService
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deploy_frontend(request, tenant_id):
    """
    Deploy frontend for a specific tenant

    POST /api/deployment/{tenant_id}/deploy/

    Requires superadmin or tenant admin permissions
    """
    # Ensure we're in public schema to access Tenant model
    with schema_context(get_public_schema_name()):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if already deploying
        if tenant.deployment_status == 'deploying':
            return Response(
                {"error": "Deployment already in progress"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already deployed
        if tenant.deployment_status == 'deployed' and tenant.vercel_project_id:
            return Response(
                {
                    "message": "Frontend already deployed",
                    "url": tenant.frontend_url,
                    "project_id": tenant.vercel_project_id
                },
                status=status.HTTP_200_OK
            )

        # Update status to deploying
        tenant.deployment_status = 'deploying'
        tenant.save(update_fields=['deployment_status'])

        try:
            # Deploy to Vercel
            result = deploy_tenant_frontend(tenant)

            if result.get("success"):
                # Update tenant with deployment info
                tenant.vercel_project_id = result.get("project_id")
                tenant.frontend_url = result.get("url")
                tenant.deployment_status = 'deployed'
                tenant.save(update_fields=['vercel_project_id', 'frontend_url', 'deployment_status'])

                logger.info(f"Frontend deployed for tenant {tenant.schema_name}: {result.get('url')}")

                return Response({
                    "success": True,
                    "message": "Frontend deployed successfully",
                    "url": result.get("url"),
                    "project_id": result.get("project_id"),
                    "project_name": result.get("project_name")
                }, status=status.HTTP_201_CREATED)
            else:
                # Deployment failed
                tenant.deployment_status = 'failed'
                tenant.save(update_fields=['deployment_status'])

                logger.error(f"Failed to deploy frontend for {tenant.schema_name}: {result.get('error')}")

                return Response({
                    "success": False,
                    "error": result.get("error", "Deployment failed"),
                    "code": result.get("code", "UNKNOWN")
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            # Reset status on error
            tenant.deployment_status = 'failed'
            tenant.save(update_fields=['deployment_status'])

            logger.exception(f"Exception during deployment for {tenant.schema_name}")

            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_deployment_status(request, tenant_id):
    """
    Get deployment status for a tenant

    GET /api/deployment/{tenant_id}/status/
    """
    with schema_context(get_public_schema_name()):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        response_data = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "deployment_status": tenant.deployment_status,
            "frontend_url": tenant.frontend_url,
            "vercel_project_id": tenant.vercel_project_id
        }

        # If deployed, get latest deployment info from Vercel
        if tenant.vercel_project_id and tenant.deployment_status == 'deployed':
            try:
                service = VercelDeploymentService()
                project_info = service.get_project(tenant.vercel_project_id)
                if project_info.get("success"):
                    response_data["vercel_info"] = {
                        "project_name": project_info.get("name"),
                        "framework": project_info.get("framework"),
                        "latest_deployments": project_info.get("latest_deployments", [])[:3]  # Last 3 deployments
                    }
            except Exception as e:
                logger.warning(f"Could not fetch Vercel project info: {e}")

        return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeploy_frontend(request, tenant_id):
    """
    Trigger a redeployment for an existing tenant frontend

    POST /api/deployment/{tenant_id}/redeploy/
    """
    with schema_context(get_public_schema_name()):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not tenant.vercel_project_id:
            return Response(
                {"error": "No deployment found. Use deploy endpoint first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = VercelDeploymentService()
            project_name = f"store-{tenant.schema_name}".lower().replace("_", "-")
            result = service.trigger_deployment(project_name)

            if result.get("success"):
                return Response({
                    "success": True,
                    "message": "Redeployment triggered",
                    "deployment_id": result.get("deployment_id"),
                    "url": result.get("url"),
                    "state": result.get("ready_state")
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "error": result.get("error")
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"Failed to redeploy for {tenant.schema_name}")
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_deployment(request, tenant_id):
    """
    Delete a Vercel deployment for a tenant

    DELETE /api/deployment/{tenant_id}/delete/

    This removes the Vercel project completely
    """
    with schema_context(get_public_schema_name()):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not tenant.vercel_project_id:
            return Response(
                {"error": "No deployment found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = VercelDeploymentService()
            result = service.delete_project(tenant.vercel_project_id)

            if result.get("success"):
                # Clear deployment info
                old_project_id = tenant.vercel_project_id
                tenant.vercel_project_id = None
                tenant.frontend_url = None
                tenant.deployment_status = 'pending'
                tenant.save(update_fields=['vercel_project_id', 'frontend_url', 'deployment_status'])

                logger.info(f"Deleted Vercel project {old_project_id} for tenant {tenant.schema_name}")

                return Response({
                    "success": True,
                    "message": "Deployment deleted successfully"
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "error": result.get("error")
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"Failed to delete deployment for {tenant.schema_name}")
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_deployment_env(request, tenant_id):
    """
    Update environment variables for an existing deployment

    PUT /api/deployment/{tenant_id}/env/

    Body:
    {
        "env_vars": [
            {"key": "NEXT_PUBLIC_STORE_NAME", "value": "New Store Name"}
        ]
    }
    """
    with schema_context(get_public_schema_name()):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not tenant.vercel_project_id:
            return Response(
                {"error": "No deployment found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        env_vars = request.data.get("env_vars", [])
        if not env_vars:
            return Response(
                {"error": "No environment variables provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = VercelDeploymentService()
            result = service.add_environment_variables(tenant.vercel_project_id, env_vars)

            if result.get("success"):
                return Response({
                    "success": True,
                    "message": f"Updated {result.get('updated')} environment variables",
                    "note": "You may need to redeploy for changes to take effect"
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "error": result.get("error")
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"Failed to update env vars for {tenant.schema_name}")
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
