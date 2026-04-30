from django.urls import path
from .views import FollowView, FollowersListView, FollowingListView, ReactionView

urlpatterns = [
    path('users/<int:user_id>/follow/', FollowView.as_view(), name='user-follow'),
    path('users/<int:user_id>/followers/', FollowersListView.as_view(), name='user-followers'),
    path('users/<int:user_id>/following/', FollowingListView.as_view(), name='user-following'),
    # SOC2 — Project reaction
    path('projects/<uuid:project_id>/react/', ReactionView.as_view(), name='project-react'),
]
