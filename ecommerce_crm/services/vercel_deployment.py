"""
Vercel Deployment Service for E-commerce Frontend

This service handles automated deployment of tenant-specific
e-commerce frontends to Vercel.
"""
import requests
import logging
import time
from django.conf import settings
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class VercelDeploymentService:
    """Service for managing Vercel deployments via REST API"""

    BASE_URL = "https://api.vercel.com"

    def __init__(self):
        self.token = getattr(settings, 'VERCEL_TOKEN', '')
        self.team_id = getattr(settings, 'VERCEL_TEAM_ID', '')
        self.github_repo = getattr(settings, 'VERCEL_GITHUB_REPO', '')

        if not self.token:
            raise ValueError("VERCEL_TOKEN not configured in settings")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _get_team_param(self) -> str:
        """Get team ID query parameter if configured"""
        return f"?teamId={self.team_id}" if self.team_id else ""

    def get_project_domains(self, project_id: str) -> Dict[str, Any]:
        """
        Get all domains/aliases for a project including the production URL

        Args:
            project_id: Vercel project ID or name

        Returns:
            Dict with production_url and all domains
        """
        url = f"{self.BASE_URL}/v9/projects/{project_id}{self._get_team_param()}"

        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()

            # Extract domains from project data
            targets = data.get("targets", {})
            production_target = targets.get("production", {})

            # Get the production alias (the .vercel.app URL)
            alias = production_target.get("alias", [])

            # Look for the main .vercel.app domain
            production_url = None
            for domain in alias:
                if ".vercel.app" in domain:
                    production_url = f"https://{domain}"
                    break

            # If no .vercel.app found, construct it from project name
            if not production_url:
                project_name = data.get("name", "")
                if project_name:
                    production_url = f"https://{project_name}.vercel.app"

            return {
                "success": True,
                "production_url": production_url,
                "all_domains": alias,
                "project_name": data.get("name"),
                "latest_deployments": data.get("latestDeployments", [])
            }
        else:
            return {
                "success": False,
                "error": "Failed to fetch project domains"
            }

    def wait_for_deployment(self, project_id: str, max_wait: int = 300) -> Dict[str, Any]:
        """
        Wait for the latest deployment to be ready

        Args:
            project_id: Project ID or name
            max_wait: Maximum seconds to wait (default 5 minutes)

        Returns:
            Deployment status and URL when ready
        """
        start_time = time.time()
        poll_interval = 10  # Poll every 10 seconds

        while time.time() - start_time < max_wait:
            project_info = self.get_project_domains(project_id)

            if not project_info.get("success"):
                time.sleep(poll_interval)
                continue

            latest_deployments = project_info.get("latest_deployments", [])

            if latest_deployments:
                latest = latest_deployments[0]
                state = latest.get("readyState", "")

                if state == "READY":
                    # Deployment is complete
                    return {
                        "success": True,
                        "state": state,
                        "production_url": project_info.get("production_url"),
                        "deployment_url": latest.get("url"),
                        "created_at": latest.get("createdAt")
                    }
                elif state in ["ERROR", "CANCELED"]:
                    return {
                        "success": False,
                        "state": state,
                        "error": f"Deployment {state.lower()}"
                    }
                else:
                    # Still building/queued
                    logger.info(f"Deployment state: {state}, waiting...")
                    time.sleep(poll_interval)
            else:
                time.sleep(poll_interval)

        return {
            "success": False,
            "error": f"Deployment did not complete within {max_wait} seconds"
        }

    def create_project(self, project_name: str, env_vars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a new Vercel project for a tenant

        Args:
            project_name: Unique project name (e.g., store-demo)
            env_vars: List of environment variable dicts

        Returns:
            Project creation response including project ID and URLs
        """
        url = f"{self.BASE_URL}/v9/projects{self._get_team_param()}"

        # Prepare environment variables in Vercel format
        formatted_env_vars = []
        for env in env_vars:
            formatted_env_vars.append({
                "key": env["key"],
                "value": str(env["value"]),
                "target": ["production", "preview", "development"],
                "type": "plain"
            })

        payload = {
            "name": project_name,
            "framework": "nextjs",
            "gitRepository": {
                "type": "github",
                "repo": self.github_repo
            },
            "environmentVariables": formatted_env_vars
        }

        logger.info(f"Creating Vercel project: {project_name}")

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == 200:
            project_data = response.json()
            logger.info(f"Project created successfully: {project_data.get('id')}")
            return {
                "success": True,
                "project_id": project_data.get("id"),
                "project_name": project_data.get("name"),
                "account_id": project_data.get("accountId"),
                "created_at": project_data.get("createdAt"),
                "framework": project_data.get("framework"),
                "url": f"https://{project_name}.vercel.app"
            }
        else:
            error_data = response.json()
            logger.error(f"Failed to create project: {error_data}")
            return {
                "success": False,
                "error": error_data.get("error", {}).get("message", "Unknown error"),
                "code": error_data.get("error", {}).get("code", "UNKNOWN")
            }

    def add_environment_variables(self, project_id: str, env_vars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Add or update environment variables for a project

        Args:
            project_id: Vercel project ID
            env_vars: List of {key, value} dicts

        Returns:
            Operation result
        """
        url = f"{self.BASE_URL}/v9/projects/{project_id}/env{self._get_team_param()}"
        if "?" in url:
            url += "&upsert=true"
        else:
            url += "?upsert=true"

        # Format for batch update
        formatted_vars = []
        for env in env_vars:
            formatted_vars.append({
                "key": env["key"],
                "value": str(env["value"]),
                "target": ["production", "preview", "development"],
                "type": "plain"
            })

        response = requests.post(url, headers=self.headers, json=formatted_vars)

        if response.status_code in [200, 201]:
            logger.info(f"Environment variables updated for project {project_id}")
            return {"success": True, "updated": len(formatted_vars)}
        else:
            error_data = response.json()
            logger.error(f"Failed to update env vars: {error_data}")
            return {
                "success": False,
                "error": error_data.get("error", {}).get("message", "Unknown error")
            }

    def trigger_deployment(self, project_name: str) -> Dict[str, Any]:
        """
        Trigger a new deployment for a project

        Args:
            project_name: Project name or ID

        Returns:
            Deployment information
        """
        url = f"{self.BASE_URL}/v13/deployments{self._get_team_param()}"

        payload = {
            "name": project_name,
            "gitSource": {
                "type": "github",
                "repo": self.github_repo,
                "ref": "main"  # Deploy from main branch
            }
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code in [200, 201]:
            deployment_data = response.json()
            logger.info(f"Deployment triggered: {deployment_data.get('id')}")
            return {
                "success": True,
                "deployment_id": deployment_data.get("id"),
                "url": deployment_data.get("url"),
                "ready_state": deployment_data.get("readyState"),
                "created_at": deployment_data.get("createdAt")
            }
        else:
            error_data = response.json()
            logger.error(f"Failed to trigger deployment: {error_data}")
            return {
                "success": False,
                "error": error_data.get("error", {}).get("message", "Unknown error")
            }

    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get the status of a deployment

        Args:
            deployment_id: Vercel deployment ID

        Returns:
            Deployment status information
        """
        url = f"{self.BASE_URL}/v13/deployments/{deployment_id}{self._get_team_param()}"

        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "id": data.get("id"),
                "state": data.get("readyState"),
                "url": data.get("url"),
                "created_at": data.get("createdAt"),
                "ready_at": data.get("ready"),
                "alias": data.get("alias", [])
            }
        else:
            return {"success": False, "error": "Failed to get deployment status"}

    def get_project(self, project_name: str) -> Dict[str, Any]:
        """
        Get project information

        Args:
            project_name: Project name or ID

        Returns:
            Project information
        """
        url = f"{self.BASE_URL}/v9/projects/{project_name}{self._get_team_param()}"

        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "id": data.get("id"),
                "name": data.get("name"),
                "framework": data.get("framework"),
                "latest_deployments": data.get("latestDeployments", [])
            }
        else:
            return {"success": False, "error": "Project not found"}

    def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Delete a Vercel project

        Args:
            project_id: Project ID to delete

        Returns:
            Operation result
        """
        url = f"{self.BASE_URL}/v9/projects/{project_id}{self._get_team_param()}"

        response = requests.delete(url, headers=self.headers)

        if response.status_code in [200, 204]:
            logger.info(f"Project {project_id} deleted successfully")
            return {"success": True}
        else:
            error_data = response.json() if response.text else {}
            logger.error(f"Failed to delete project: {error_data}")
            return {
                "success": False,
                "error": error_data.get("error", {}).get("message", "Unknown error")
            }


def deploy_tenant_frontend(tenant) -> Dict[str, Any]:
    """
    High-level function to deploy a tenant's e-commerce frontend

    Args:
        tenant: Tenant model instance

    Returns:
        Deployment result with URL and status
    """
    service = VercelDeploymentService()

    # Generate project name (must be URL-safe)
    project_name = f"store-{tenant.schema_name}".lower().replace("_", "-")

    # Prepare environment variables from tenant configuration
    env_vars = [
        {"key": "NEXT_PUBLIC_TENANT_ID", "value": str(tenant.id)},
        {"key": "NEXT_PUBLIC_TENANT_SCHEMA", "value": tenant.schema_name},
        {"key": "NEXT_PUBLIC_API_URL", "value": f"https://{tenant.schema_name}.api.echodesk.ge"},
        {"key": "NEXT_PUBLIC_STORE_NAME", "value": tenant.name},
        {"key": "NEXT_PUBLIC_STORE_DESCRIPTION", "value": getattr(tenant, 'description', 'Welcome to our store')},
        {"key": "NEXT_PUBLIC_STORE_LOGO", "value": getattr(tenant, 'logo_url', '')},
        {"key": "NEXT_PUBLIC_PRIMARY_COLOR", "value": ""},  # Use default colors
        {"key": "NEXT_PUBLIC_SECONDARY_COLOR", "value": ""},
        {"key": "NEXT_PUBLIC_ACCENT_COLOR", "value": ""},
        {"key": "NEXT_PUBLIC_CURRENCY", "value": "GEL"},
        {"key": "NEXT_PUBLIC_LOCALE", "value": "en"},
        {"key": "NEXT_PUBLIC_ENABLE_WISHLIST", "value": "true"},
        {"key": "NEXT_PUBLIC_ENABLE_REVIEWS", "value": "false"},
        {"key": "NEXT_PUBLIC_ENABLE_COMPARE", "value": "false"},
        {"key": "NEXT_PUBLIC_FACEBOOK_URL", "value": ""},
        {"key": "NEXT_PUBLIC_INSTAGRAM_URL", "value": ""},
        {"key": "NEXT_PUBLIC_TWITTER_URL", "value": ""},
        {"key": "NEXT_PUBLIC_CONTACT_EMAIL", "value": getattr(tenant, 'email', f"support@{tenant.schema_name}.echodesk.ge")},
        {"key": "NEXT_PUBLIC_CONTACT_PHONE", "value": getattr(tenant, 'phone', '')},
        {"key": "NEXT_PUBLIC_CONTACT_ADDRESS", "value": getattr(tenant, 'address', '')},
        {"key": "NEXT_PUBLIC_GA_ID", "value": ""},
        {"key": "NEXT_PUBLIC_GTM_ID", "value": ""},
        {"key": "NEXT_PUBLIC_IMAGE_HOSTNAMES", "value": "echodesk-spaces.fra1.digitaloceanspaces.com"},
    ]

    # Create project with environment variables
    result = service.create_project(project_name, env_vars)

    if result.get("success"):
        project_id = result.get("project_id")

        # Trigger a deployment after creating the project
        logger.info(f"Triggering deployment for project {project_name}...")
        deployment_result = service.trigger_deployment(project_name)

        if deployment_result.get("success"):
            logger.info(f"Deployment triggered: {deployment_result.get('deployment_id')}")

            # Wait for deployment to be ready (with timeout)
            wait_result = service.wait_for_deployment(project_id, max_wait=300)

            if wait_result.get("success"):
                result["url"] = wait_result.get("production_url")
                result["deployment_url"] = wait_result.get("deployment_url")
                logger.info(f"Tenant {tenant.schema_name} frontend deployed successfully. URL: {result['url']}")
            else:
                # Deployment didn't complete in time or failed
                logger.warning(f"Deployment did not complete: {wait_result.get('error')}")
                # Still return the expected URL
                result["url"] = f"https://{project_name}.vercel.app"
        else:
            logger.warning(f"Failed to trigger deployment: {deployment_result.get('error')}")
            # Fallback to constructed URL
            result["url"] = f"https://{project_name}.vercel.app"

        # Fetch final domain info
        domains_info = service.get_project_domains(project_id)
        if domains_info.get("success"):
            result["all_domains"] = domains_info.get("all_domains", [])
            # Use actual URL if available and we don't have one yet
            if not result.get("url") or result.get("url") == f"https://{project_name}.vercel.app":
                actual_url = domains_info.get("production_url")
                if actual_url:
                    result["url"] = actual_url
    else:
        logger.error(f"Failed to deploy frontend for {tenant.schema_name}: {result.get('error')}")

    return result
