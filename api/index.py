from app import app

# Vercel serverless function handler
def handler(request):
    return app(request.environ, lambda status, headers: None)

# For Vercel
application = app

if __name__ == "__main__":
    app.run()
