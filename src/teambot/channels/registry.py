from __future__ import annotations

from .base import ChannelAdapter
from .models import ChannelId
from .plugins.discord import DiscordChannelAdapter
from .plugins.feishu import FeishuChannelAdapter
from .plugins.generic import GenericJsonMessageChannelAdapter
from .plugins.slack import SlackChannelAdapter
from .plugins.telegram import TelegramChannelAdapter
from .plugins.whatsapp import WhatsAppChannelAdapter

_CHANNEL_IDS: tuple[ChannelId, ...] = (
    "whatsapp",
    "slack",
    "telegram",
    "discord",
    "feishu",
)
_CHANNEL_ADAPTERS: dict[ChannelId, ChannelAdapter] = {
    "whatsapp": WhatsAppChannelAdapter(),
    "slack": SlackChannelAdapter(),
    "telegram": TelegramChannelAdapter(),
    "discord": DiscordChannelAdapter(),
    "feishu": FeishuChannelAdapter(),
}


def list_channel_ids() -> list[str]:
    return list(_CHANNEL_IDS)


def get_channel_adapter(channel_id: str) -> ChannelAdapter | None:
    normalized = channel_id.strip().lower()
    if not normalized:
        return None
    return _CHANNEL_ADAPTERS.get(normalized)  # type: ignore[arg-type]
