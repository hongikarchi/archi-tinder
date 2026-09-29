from django.urls import path
from .views import (
    ProjectReactorsListView,
    ReactionView,
    UserSavedStudiosView,
)
from .views_people import PeopleDiscoveryView, PeopleReportImageView

urlpatterns = [
    path('users/<int:user_id>/saved_studios/', UserSavedStudiosView.as_view(), name='user-saved-studios'),
    # SOC2 — Project reaction
    path('projects/<uuid:project_id>/react/', ReactionView.as_view(), name='project-react'),
    path(
        'projects/<uuid:project_id>/reactors/',
        ProjectReactorsListView.as_view(),
        name='project-reactors',
    ),
    # Personality-based people discovery
    path('people/', PeopleDiscoveryView.as_view(), name='people-discovery'),
    path(
        'people/<int:user_id>/report-image/',
        PeopleReportImageView.as_view(),
        name='people-report-image',
    ),
]
