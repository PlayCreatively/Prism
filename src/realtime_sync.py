"""
Real-Time Synchronization for PRISM.

Handles Supabase Realtime subscriptions for live updates
and integrates with NiceGUI for reactive UI updates.
"""

import logging
import asyncio
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RealtimeEvent:
    """Represents a real-time event from Supabase."""
    event_type: str  # 'INSERT', 'UPDATE', 'DELETE'
    table: str  # 'nodes', 'user_node_votes', etc.
    record: Dict[str, Any]
    old_record: Optional[Dict[str, Any]] = None


@dataclass
class SyncState:
    """Tracks the sync state of the application."""
    is_connected: bool = False
    last_event_time: Optional[float] = None
    pending_events: List[RealtimeEvent] = field(default_factory=list)
    error_count: int = 0
    reconnect_attempts: int = 0


class RealtimeSyncManager:
    """
    Manages real-time synchronization with Supabase.
    
    Features:
    - Subscribe to node and vote changes
    - Debounce rapid updates
    - Handle reconnection
    - Integrate with NiceGUI for UI updates
    """
    
    def __init__(
        self,
        backend=None,
        debounce_ms: int = 100,
        max_reconnect_attempts: int = 5
    ):
        """
        Initialize RealtimeSyncManager.
        
        Args:
            backend: SupabaseBackend instance
            debounce_ms: Debounce time for rapid updates
            max_reconnect_attempts: Max reconnection attempts before giving up
        """
        self._backend = backend
        self._debounce_ms = debounce_ms
        self._max_reconnect = max_reconnect_attempts
        
        self._state = SyncState()
        self._callbacks: Dict[str, List[Callable]] = {
            'node_insert': [],
            'node_update': [],
            'node_delete': [],
            'vote_change': [],
            'connection_change': [],
            'error': []
        }
        
        self._debounce_task: Optional[asyncio.Task] = None
        self._pending_updates: Dict[str, RealtimeEvent] = {}
    
    @property
    def is_connected(self) -> bool:
        """Check if real-time connection is active."""
        return self._state.is_connected
    
    def on(self, event: str, callback: Callable) -> None:
        """
        Register a callback for an event type.
        
        Event types:
        - 'node_insert': New node created
        - 'node_update': Node properties changed
        - 'node_delete': Node deleted
        - 'vote_change': User vote changed
        - 'connection_change': Connection state changed
        - 'error': Sync error occurred
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def off(self, event: str, callback: Callable) -> None:
        """Remove a callback for an event type."""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)
    
    def _emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                result = callback(data)
                # Handle async callbacks
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in callback for {event}: {e}")
    
    def start(self) -> None:
        """Start listening for real-time updates."""
        if not self._backend:
            logger.warning("No backend configured for realtime sync")
            return
        
        if not self._backend.supports_realtime:
            logger.info("Backend does not support realtime sync")
            return
        
        def on_node_change(event_type: str, node_id: str, data: Dict[str, Any]):
            self._handle_node_event(event_type, node_id, data)
        
        def on_vote_change(event_type: str, node_id: str, data: Dict[str, Any]):
            self._handle_vote_event(event_type, node_id, data)
        
        try:
            self._backend.subscribe(
                on_node_change=on_node_change,
                on_vote_change=on_vote_change
            )
            self._state.is_connected = True
            self._state.reconnect_attempts = 0
            self._emit('connection_change', {'connected': True})
            logger.info("Real-time sync started")
        except Exception as e:
            logger.error(f"Failed to start realtime sync: {e}")
            self._state.error_count += 1
            self._emit('error', {'message': str(e)})
    
    def stop(self) -> None:
        """Stop listening for real-time updates."""
        if self._backend:
            self._backend.unsubscribe()
        
        self._state.is_connected = False
        self._emit('connection_change', {'connected': False})
        logger.info("Real-time sync stopped")
    
    def _handle_node_event(self, event_type: str, node_id: str, data: Dict[str, Any]) -> None:
        """Handle a node change event."""
        import time
        self._state.last_event_time = time.time()
        
        event = RealtimeEvent(
            event_type=event_type,
            table='nodes',
            record=data
        )
        
        # Debounce updates to the same node
        self._pending_updates[f"node:{node_id}"] = event
        self._schedule_flush()
    
    def _handle_vote_event(self, event_type: str, node_id: str, data: Dict[str, Any]) -> None:
        """Handle a vote change event."""
        import time
        self._state.last_event_time = time.time()
        
        event = RealtimeEvent(
            event_type=event_type,
            table='user_node_votes',
            record=data
        )
        
        # Debounce by node_id + user_id
        user_id = data.get('user_id', '')
        self._pending_updates[f"vote:{node_id}:{user_id}"] = event
        self._schedule_flush()
    
    def _schedule_flush(self) -> None:
        """Schedule a flush of pending updates after debounce period."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        
        async def flush():
            await asyncio.sleep(self._debounce_ms / 1000)
            self._flush_pending()
        
        self._debounce_task = asyncio.create_task(flush())
    
    def _flush_pending(self) -> None:
        """Flush all pending updates."""
        updates = dict(self._pending_updates)
        self._pending_updates.clear()
        
        for key, event in updates.items():
            if event.table == 'nodes':
                if event.event_type == 'INSERT':
                    self._emit('node_insert', event.record)
                elif event.event_type == 'UPDATE':
                    self._emit('node_update', event.record)
                elif event.event_type == 'DELETE':
                    self._emit('node_delete', event.record)
            elif event.table == 'user_node_votes':
                self._emit('vote_change', event.record)


class NiceGUIRealtimeAdapter:
    """
    Adapter that integrates RealtimeSyncManager with NiceGUI.
    
    Provides automatic UI updates when remote changes occur.
    """
    
    def __init__(self, sync_manager: RealtimeSyncManager):
        """
        Initialize adapter.
        
        Args:
            sync_manager: The RealtimeSyncManager to adapt
        """
        self._sync = sync_manager
        self._refresh_callback: Optional[Callable] = None
        self._status_element = None
        
        # Register handlers
        self._sync.on('node_insert', self._on_node_change)
        self._sync.on('node_update', self._on_node_change)
        self._sync.on('node_delete', self._on_node_change)
        self._sync.on('vote_change', self._on_vote_change)
        self._sync.on('connection_change', self._on_connection_change)
        self._sync.on('error', self._on_error)
    
    def set_refresh_callback(self, callback: Callable) -> None:
        """Set the callback to refresh the graph UI."""
        self._refresh_callback = callback
    
    def _on_node_change(self, data: Dict[str, Any]) -> None:
        """Handle node changes."""
        from nicegui import ui
        
        node_label = data.get('label', 'A node')
        ui.notify(f'📝 {node_label} was updated', timeout=2000)
        
        if self._refresh_callback:
            self._refresh_callback()
    
    def _on_vote_change(self, data: Dict[str, Any]) -> None:
        """Handle vote changes."""
        if self._refresh_callback:
            self._refresh_callback()
    
    def _on_connection_change(self, data: Dict[str, Any]) -> None:
        """Handle connection state changes."""
        from nicegui import ui
        
        connected = data.get('connected', False)
        
        if connected:
            ui.notify('🟢 Real-time sync connected', color='positive', timeout=2000)
        else:
            ui.notify('🔴 Real-time sync disconnected', color='warning', timeout=3000)
        
        self._update_status_indicator(connected)
    
    def _on_error(self, data: Dict[str, Any]) -> None:
        """Handle sync errors."""
        from nicegui import ui
        
        message = data.get('message', 'Unknown error')
        ui.notify(f'⚠️ Sync error: {message}', color='negative', timeout=5000)
    
    def _update_status_indicator(self, connected: bool) -> None:
        """Update the connection status indicator if it exists."""
        if self._status_element:
            try:
                if connected:
                    self._status_element.classes(replace='bg-green-500')
                    self._status_element.tooltip('Real-time sync active')
                else:
                    self._status_element.classes(replace='bg-red-500')
                    self._status_element.tooltip('Real-time sync disconnected')
            except Exception:
                pass
    
    def render_status_indicator(self):
        """
        Render a connection status indicator.
        
        Returns a small colored dot indicating sync status.
        """
        from nicegui import ui
        
        connected = self._sync.is_connected
        color_class = 'bg-green-500' if connected else 'bg-gray-500'
        tooltip = 'Real-time sync active' if connected else 'Connecting...'
        
        with ui.element('div').classes(f'{color_class} w-2 h-2 rounded-full') as indicator:
            indicator.tooltip(tooltip)
        
        self._status_element = indicator
        return indicator


def create_realtime_sync(backend=None) -> tuple[RealtimeSyncManager, NiceGUIRealtimeAdapter]:
    """
    Create and configure real-time sync for a project.
    
    Args:
        backend: SupabaseBackend instance
        
    Returns:
        Tuple of (RealtimeSyncManager, NiceGUIRealtimeAdapter)
    """
    sync_manager = RealtimeSyncManager(backend=backend)
    adapter = NiceGUIRealtimeAdapter(sync_manager)
    
    return sync_manager, adapter
