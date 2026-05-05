from django.urls import path
from .views import CalculateRouteView

urlpatterns = [
    path('calculate-route/', CalculateRouteView.as_view(), name='calculate-route'),
]
