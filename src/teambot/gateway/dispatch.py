from __future__ import annotations

from ..channels.models import ChannelEnvelope
from ..domain.models import InboundEvent


def envelope_to_inbound_event(envelope: ChannelEnvelope) -> InboundEvent:
    metadata = envelope.metadata
    team_id = str(
        metadata.get("workspace_id")
        or metadata.get("team_id")
        or metadata.get("guild_id")
        or envelope.account_id
        or envelope.channel
    )
    thread_ts = envelope.thread_id or envelope.conversation_id
    return InboundEvent(
        event_id=envelope.event_id,
        event_type="message",
        team_id=team_id,
        channel_id=envelope.conversation_id,
        thread_ts=thread_ts,
        user_id=envelope.sender_id,
        text=envelope.text,
    )
