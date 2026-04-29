from rest_framework import serializers
from .models import Office


class OfficeProjectLinkInlineSerializer(serializers.Serializer):
    """Project card embed shape inside OfficeSerializer.projects[]."""
    building_id = serializers.CharField()
    name_en = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.URLField(required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)
    program = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)


class OfficeSerializer(serializers.ModelSerializer):
    """Matches designer's MOCK_OFFICE shape per FirmProfilePage.jsx.

    `projects` is NOT declared as a class attribute (the model's reverse relation is
    named 'project_links', not 'projects', so a class-level declaration would be dead
    code and cause attribute resolution errors). OfficeDetailView injects
    `data['projects'] = projects` post-serialization via raw SQL + OfficeProjectLink.
    The field is also excluded from Meta.fields so DRF does not try to auto-resolve it.

    Field parity vs MOCK_OFFICE (FirmProfilePage.jsx line ~35):
      MOCK_OFFICE key       -> Serializer field
      --------------------------------
      office_id             -> office_id   (UUID; MOCK uses short string 'OFF001' — opaque to frontend, OK)
      name                  -> name
      verified              -> verified
      website_url           -> website_url (source='website'; MOCK uses 'website_url', model stores as 'website')
      contact_email         -> contact_email
      description           -> description
      logo_url              -> logo_url
      location              -> location
      founded_year          -> founded_year
      follower_count        -> follower_count
      following_count       -> following_count
      projects[]            -> injected by OfficeDetailView post-serialization
      articles[]            -> EXCLUDED   (Phase 18 External — deferred)
    """
    # Map model field 'website' -> response key 'website_url' to match MOCK_OFFICE shape
    website_url = serializers.URLField(source='website', allow_blank=True, required=False)

    class Meta:
        model = Office
        fields = [
            'office_id', 'name', 'verified', 'website_url', 'contact_email',
            'description', 'logo_url', 'location', 'founded_year',
            'follower_count', 'following_count',
        ]
        # claim_status, aliases, canonical_id excluded from public API
        # (administrative fields; admin queue endpoint exposes them separately)
        # 'projects' excluded from Meta.fields — injected post-serialization by view


class OfficeClaimSerializer(serializers.Serializer):
    """POST /api/v1/offices/{office_id}/claim/ payload — v0 conservative.

    Fix-loop 1 hardening: contact_email and website removed from schema. Claim does NOT
    mutate Office contact fields before admin verification. Admin reaches out to claimant
    via Django User auth context (request.user) for verification correspondence and
    updates contact fields manually post-verification via admin endpoints if needed.

    Breaking change from PROF1: callers passing contact_email / website will have those
    fields silently ignored (not in schema). Frontend claim form does not yet exist
    (designer pipeline territory), so no active frontend impact.
    """
    proof_text = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class OfficeAdminSerializer(serializers.ModelSerializer):
    """Admin-only -- exposes claim_status + canonical_id for review queue."""
    class Meta:
        model = Office
        fields = '__all__'
