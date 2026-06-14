from django.urls import path
from .views import (
    ProjectReactorsListView,
    ReactionView,
    UserSavedStudiosView,
)

urlpatterns = [
    path('users/<int:user_id>/saved_studios/', UserSavedStudiosView.as_view(), name='user-saved-studios'),
    # SOC2 — Project reaction
    path('projects/<uuid:project_id>/react/', ReactionView.as_view(), name='project-react'),
    path(
        'projects/<uuid:project_id>/reactors/',
        ProjectReactorsListView.as_view(),
        name='project-reactors',
    ),
]
