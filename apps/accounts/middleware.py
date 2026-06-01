class NoCacheAuthenticatedMiddleware:
    """Prevent browsers from caching pages served to authenticated users.

    Without this, hitting Back after logout can re-display the previous page
    from the browser's bfcache, leaking session-bound data.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
