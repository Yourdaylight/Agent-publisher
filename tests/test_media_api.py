from __future__ import annotations

import sys
import types
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Third-party stubs
# ---------------------------------------------------------------------------
credential_module = types.ModuleType('tencentcloud.common.credential')
credential_module.Credential = object
client_profile_module = types.ModuleType('tencentcloud.common.profile.client_profile')
client_profile_module.ClientProfile = object
http_profile_module = types.ModuleType('tencentcloud.common.profile.http_profile')
http_profile_module.HttpProfile = object
aiart_client_module = types.ModuleType('tencentcloud.aiart.v20221229.aiart_client')
aiart_client_module.AiartClient = object
models_module = types.ModuleType('tencentcloud.aiart.v20221229.models')
models_module.SubmitTextToImageJobRequest = object
models_module.QueryTextToImageJobRequest = object
feedparser_module = types.ModuleType('feedparser')
feedparser_module.parse = lambda *_args, **_kwargs: SimpleNamespace(entries=[], feed={})

sys.modules.setdefault('tencentcloud', types.ModuleType('tencentcloud'))
sys.modules.setdefault('tencentcloud.common', types.ModuleType('tencentcloud.common'))
sys.modules.setdefault('tencentcloud.common.profile', types.ModuleType('tencentcloud.common.profile'))
sys.modules.setdefault('tencentcloud.aiart', types.ModuleType('tencentcloud.aiart'))
sys.modules.setdefault('tencentcloud.aiart.v20221229', types.ModuleType('tencentcloud.aiart.v20221229'))
sys.modules['feedparser'] = feedparser_module
sys.modules['tencentcloud.common.credential'] = credential_module
sys.modules['tencentcloud.common.profile.client_profile'] = client_profile_module
sys.modules['tencentcloud.common.profile.http_profile'] = http_profile_module
sys.modules['tencentcloud.aiart.v20221229.aiart_client'] = aiart_client_module
sys.modules['tencentcloud.aiart.v20221229.models'] = models_module

from agent_publisher.api.media import _serialize_media_asset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mapping(
    id_: int = 1,
    account_id: int = 1,
    wechat_url: str = '',
    upload_status: str = 'pending',
    error_message: str = '',
):
    return SimpleNamespace(
        id=id_,
        account_id=account_id,
        wechat_url=wechat_url,
        upload_status=upload_status,
        error_message=error_message,
        uploaded_at=None,
        created_at=None,
        updated_at=None,
    )


def _make_asset(id_: int = 1, mappings=None, **kwargs):
    defaults = dict(
        filename='img.png',
        stored_filename='s.png',
        content_type='image/png',
        file_size=1024,
        tags=[],
        description='',
        owner_email='t@t.com',
        source_kind='manual',
        source_url='',
        article_id=None,
        created_at=None,
    )
    defaults.update(kwargs)
    defaults['wechat_mappings'] = mappings or []
    return SimpleNamespace(id=id_, **defaults)


# ===========================================================================
# Upload status aggregation tests
# ===========================================================================

class TestSerializeMediaAssetUploadStatus:
    """Verify the latest_upload_status aggregation priority."""

    def test_failed_overrides_everything(self):
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=1, upload_status='success'),
            _make_mapping(id_=2, account_id=2, upload_status='failed', error_message='err'),
        ])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == 'failed'

    def test_processing_overrides_success(self):
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=1, upload_status='success'),
            _make_mapping(id_=2, account_id=2, upload_status='processing'),
        ])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == 'processing'

    def test_all_success(self):
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=1, upload_status='success'),
            _make_mapping(id_=2, account_id=2, upload_status='success'),
        ])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == 'success'

    def test_all_pending(self):
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=1, upload_status='pending'),
        ])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == 'pending'

    def test_no_mappings(self):
        asset = _make_asset(mappings=[])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == ''

    def test_pending_and_success_yields_pending(self):
        """Mixed pending + success → not all success, so falls to pending."""
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=1, upload_status='success'),
            _make_mapping(id_=2, account_id=2, upload_status='pending'),
        ])
        payload = _serialize_media_asset(asset)
        assert payload['latest_upload_status'] == 'pending'


# ===========================================================================
# Serialization structure tests
# ===========================================================================

class TestSerializeMediaAssetStructure:
    """Verify the serialized payload shape and field presence."""

    def test_all_required_fields_present(self):
        asset = _make_asset(id_=10, filename='test.jpg', source_kind='article_body', article_id=5)
        payload = _serialize_media_asset(asset)
        assert payload['id'] == 10
        assert payload['filename'] == 'test.jpg'
        assert payload['source_kind'] == 'article_body'
        assert payload['article_id'] == 5
        assert payload['url'] == '/api/media/10/download'
        assert 'wechat_mappings' in payload
        assert 'latest_upload_status' in payload

    def test_mappings_sorted_by_account_id(self):
        asset = _make_asset(mappings=[
            _make_mapping(id_=1, account_id=10, upload_status='success'),
            _make_mapping(id_=2, account_id=3, upload_status='pending'),
            _make_mapping(id_=3, account_id=7, upload_status='processing'),
        ])
        payload = _serialize_media_asset(asset)
        account_ids = [m['account_id'] for m in payload['wechat_mappings']]
        assert account_ids == [3, 7, 10]

    def test_mapping_fields(self):
        asset = _make_asset(mappings=[
            _make_mapping(
                id_=99,
                account_id=5,
                wechat_url='https://mmbiz.qq.com/x.png',
                upload_status='success',
                error_message='',
            ),
        ])
        payload = _serialize_media_asset(asset)
        mapping = payload['wechat_mappings'][0]
        assert mapping['id'] == 99
        assert mapping['account_id'] == 5
        assert mapping['wechat_url'] == 'https://mmbiz.qq.com/x.png'
        assert mapping['upload_status'] == 'success'
        assert mapping['error_message'] == ''

    def test_tags_default_to_empty_list(self):
        asset = _make_asset(tags=None)
        payload = _serialize_media_asset(asset)
        assert payload['tags'] == []
