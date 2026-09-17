from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AccountErasureView, CustomTokenObtainPairView, RegisterView, UserViewSet, ProfileViewSet

router = DefaultRouter()

router.register(r"users", UserViewSet, basename="user")
router.register(r"profiles", ProfileViewSet, basename="profile")

urlpatterns = [
                  path("register/", RegisterView.as_view(), name="register_view"),
                  path("erase/", AccountErasureView.as_view(), name="account_erase"),
                  path(
                      "token/",
                      CustomTokenObtainPairView.as_view(),
                      name="token_obtain_pair",
                  ),
                  path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
              ] + router.urls
