workers = 2
bind = "0.0.0.0:8080"
timeout = 120
preload_app = True


def post_fork(server, worker):
    """Dispose DB connections inherited from master after fork.
    Required when preload_app=True : forked workers must not reuse
    the master's SSL connections (causes OperationalError on first request).
    """
    from Code.extensions import db
    db.engine.dispose()
