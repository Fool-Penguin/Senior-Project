# Middleware verification module
class SecurityHeaderMiddleware:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        # Attach defense-in-depth security headers
        def custom_start_response(status, headers, exc_info=None):
            headers.append(("X-Content-Type-Options", "nosniff"))
            headers.append(("X-Frame-Options", "DENY"))
            return start_response(status, headers, exc_info)
        return self.app(environ, custom_start_response)
