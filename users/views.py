from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.openapi import OpenApiExample
from .serializers import UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer


class CustomTokenRefreshView(TokenRefreshView):
    @extend_schema(
        operation_id='refresh_token',
        summary='Refresh JWT token',
        description='Refresh the access token using a valid refresh token.',
        responses={
            200: OpenApiResponse(
                description='Token refreshed successfully',
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                            'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Invalid refresh token')
        },
        tags=['Authentication']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(
    operation_id='register_user',
    summary='Register a new user',
    description='Create a new user account with email and password. Returns user data and JWT tokens.',
    request=UserRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            response=UserProfileSerializer,
            description='User successfully created',
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'user': {
                            'id': 1,
                            'email': 'user@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'is_active': True,
                            'date_joined': '2025-01-01T12:00:00Z'
                        },
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                    }
                )
            ]
        ),
        400: OpenApiResponse(description='Validation errors')
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='login_user',
    summary='User login',
    description='Authenticate user with email and password. Returns user data and JWT tokens.',
    request=UserLoginSerializer,
    responses={
        200: OpenApiResponse(
            response=UserProfileSerializer,
            description='Login successful',
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'user': {
                            'id': 1,
                            'email': 'user@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'is_active': True,
                            'date_joined': '2025-01-01T12:00:00Z'
                        },
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                    }
                )
            ]
        ),
        400: OpenApiResponse(description='Invalid credentials')
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='get_user_profile',
    summary='Get user profile',
    description='Get the current authenticated user\'s profile information.',
    responses={
        200: OpenApiResponse(
            response=UserProfileSerializer,
            description='User profile data',
            examples=[
                OpenApiExample(
                    'Profile Response',
                    value={
                        'id': 1,
                        'email': 'user@example.com',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'is_active': True,
                        'date_joined': '2025-01-01T12:00:00Z'
                    }
                )
            ]
        ),
        401: OpenApiResponse(description='Authentication required')
    },
    tags=['User Profile']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    serializer = UserProfileSerializer(request.user)
    return Response(serializer.data)
