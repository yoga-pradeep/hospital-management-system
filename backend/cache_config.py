from flask_caching import Cache

cache = Cache()

def init_cache(app):
    
    app.config['CACHE_TYPE']            = 'RedisCache'
    app.config['CACHE_REDIS_URL']       = 'redis://localhost:6379/1'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    cache.init_app(app)