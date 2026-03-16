from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/clients/', views.api_clients, name='api_clients'),
    path('api/rebalance/', views.api_rebalance, name='api_rebalance'),
    path('api/save_session/', views.api_save_session, name='api_save_session'),
    path('api/history/', views.api_history, name='api_history'),
    path('api/update_status/', views.api_update_status, name='api_update_status'),
    path('api/holdings/', views.api_holdings, name='api_holdings'),
    path('api/model_funds/', views.api_model_funds, name='api_model_funds'),
    path('api/update_model_funds/', views.api_update_model_funds, name='api_update_model_funds'),
]
