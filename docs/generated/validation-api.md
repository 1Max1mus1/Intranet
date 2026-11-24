@wiki id=intranet-validation-api type=module domain=projects state=draft
@summary Generated function and class inventory for the disposable Intranet validation modules.
@terms Intranet, validation, generated API
@links intranet-validation-plan

# Generated Validation API

Do not edit by hand; regenerate from validation Python sources.

## `validation/__init__.py`


## `validation/auto_node.py`

- class `DiscoveredPeer`
- class `DiscoveryService`
  - `__init__self, device: str, tls_port: int, certificate, registry, listen_port: int, remote_port: int, broadcast_host: str`
  - `startself`
  - `_receive_loopself`
  - `_announce_loopself`
  - `current_peersself`
  - `closeself`
- class `AutoNode`
  - `__init__self, files: NodeFiles, port: int, discovery_port: int, remote_discovery_port: int, broadcast: str, watch: list[str]`
  - `emitself, kind: str, **values`
  - `startself`
  - `_sync_loopself`
  - `closeself`
- `main`

## `validation/corpus.py`

- `png_byteswidth: int=64, height: int=64`
- `create_corpusroot: Path, large_size: int=128 * 1024 * 1024, small_files: int=200`
- `main`

## `validation/dual_node.py`

- `pair_authcode: str, *parts: str`
- `validation_pathvalue: str`
- class `NodeFiles`
  - `__init__self, root: str, device: str, metadata: str | None, excluded: tuple[str, ...]=()`
- `parse_peervalue: str`
- `host_pairargs`
- `join_pairargs`
- `serve_filesfiles: NodeFiles`
- `sync_filesfiles: NodeFiles, host: str, port: int`
- `main`

## `validation/engine.py`

- `hash_filepath: Path`
- `safe_pathvalue: str`
- class `Record`
  - `orderself`
  - `wireself`
  - `from_wirecls, value: dict`
  - `same_payloadself, other: Record`
- class `SyncStats`
  - `mergeself, other: SyncStats`
- class `HistoryStore`
  - `__init__self, root: Path, retention_days: int=30, max_bytes: int=20 * 1024 ** 3`
  - `preserveself, source: Path, original_path: str, reason: str`
  - `entriesself`
  - `cleanupself, now_ns: int | None=None`
  - `restoreself, entry_id: str, sync_root: Path`
- class `SyncEngine`
  - `__init__self, root: Path, device: str, metadata_root: Path, excluded: tuple[str, ...]=(), history_days: int=30, history_bytes: int=20 * 1024 ** 3`
  - `_loadself`
  - `_saveself`
  - `is_excludedself, relative: str`
  - `path_forself, relative: str`
  - `_diskself`
  - `_native_idstat: os.stat_result`
  - `scanself`
  - `_scan_unlockedself`
  - `manifestself`
  - `_adoptself, remote: Record`
  - `_preserve_historyself, path: Path, relative: str, reason: str`
  - `_conflict_copyself, source: Path`
  - `_download_fromself, peer: SyncEngine, remote: Record, temporary: Path`
  - `open_recordself, requested: Record, offset: int=0`
  - `sync_fromself, peer: SyncEngine`
  - `_sync_from_unlockedself, peer: SyncEngine`
  - `_applyself, peer: SyncEngine, remote: Record, local: Record | None, stats: SyncStats, conflict: bool`
  - `restoreself, entry_id: str`

## `validation/network.py`

- class `SocketReader`
  - `__init__self, peer: RemotePeer, size: int`
  - `__enter__self`
  - `__exit__self, exc_type, exc, traceback`
  - `readself, size: int=-1`
  - `closeself`
- class `RemotePeer`
  - `__init__self, host: str, port: int, key_path: Path, certificate_path: Path, peer_certificate: Path`
  - `manifestself`
  - `open_recordself, requested: Record, offset: int=0`
  - `closeself`
- class `NodeServer`
  - `__init__self, engine: SyncEngine, key_path: Path, certificate_path: Path, peer_certificate: Path, registry: PairingRegistry, host: str='0.0.0.0', port: int=47630`
  - `startself`
  - `_accept_loopself`
  - `_handleself, raw: socket.socket`
  - `closeself`

## `validation/perf_sync.py`

- `main`

## `validation/run_checks.py`

- `v1root: Path`
- `v2root: Path`
- `v3root: Path`
- `v4root: Path, corpus: Path`
- `v5root: Path`
- `main`

## `validation/security.py`

- class `PairingError`
- `create_identityroot: Path, common_name: str`
- `fingerprintcertificate_pem: bytes`
- class `PairingRegistry`
  - `__init__self, path: Path`
  - `issue_codeself, ttl_seconds: float=60`
  - `_hashself, code: str`
  - `pairself, code: str, peer_certificate: bytes`
  - `registerself, peer_certificate: bytes`
  - `allowsself, certificate_pem: bytes`
- class `NetworkPolicy`
  - `__init__self`
  - `trustself, network_id: str`
  - `allows_syncself, network_id: str, peer_paired: bool`
- `server_contextkey_path: Path, certificate_path: Path, peer_certificate: Path`
- `client_contextkey_path: Path, certificate_path: Path, peer_certificate: Path`

## `validation/smb_baseline.py`

- `main`

## `validation/transport.py`

- class `InjectedInterruption`
- `hash_filepath: Path`
- `send_jsonsock: socket.socket, value: dict`
- `receive_exactsock: socket.socket, size: int`
- `receive_jsonsock: socket.socket`
- class `ChunkServer`
  - `__init__self, source: Path, corrupt: bool=False, host: str='127.0.0.1', port: int=0`
  - `_runself`
  - `closeself`
- class `ResumableDownloader`
  - `__init__self, host: str, port: int, destination: Path, state_root: Path, transfer_id: str`
  - `_loadself`
  - `_saveself, offset: int, total_size: int, sha256: str`
  - `_chunkself, offset: int, length: int`
  - `downloadself, chunk_size: int=1024 * 1024, interrupt_at: int | None=None, before_replace=None, after_replace=None`
