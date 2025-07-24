from rest_framework import serializers
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema_field
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True, 
        min_length=8,
        help_text="Password must be at least 8 characters long",
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text="Confirm your password",
        style={'input_type': 'password'}
    )
    email = serializers.EmailField(
        help_text="Valid email address for account registration"
    )
    first_name = serializers.CharField(
        max_length=150,
        help_text="User's first name"
    )
    last_name = serializers.CharField(
        max_length=150,
        help_text="User's last name"
    )

    class Meta:
        model = User
        fields = ('email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user authentication"""
    email = serializers.EmailField(
        help_text="User's email address"
    )
    password = serializers.CharField(
        write_only=True,
        help_text="User's password",
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password')


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""
    id = serializers.IntegerField(
        read_only=True,
        help_text="Unique user identifier"
    )
    email = serializers.EmailField(
        read_only=True,
        help_text="User's email address"
    )
    first_name = serializers.CharField(
        max_length=150,
        help_text="User's first name"
    )
    last_name = serializers.CharField(
        max_length=150,
        help_text="User's last name"
    )
    date_joined = serializers.DateTimeField(
        read_only=True,
        help_text="Date and time when the user joined"
    )
    is_active = serializers.BooleanField(
        read_only=True,
        help_text="Whether the user account is active"
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'is_active', 'date_joined')
        read_only_fields = ('id', 'email', 'date_joined', 'is_active')
