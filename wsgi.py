from app import create_app

# Create an application instance for the WSGI server
app = create_app()

if __name__ == "__main__":
    # This allows running the app directly for local development
    # In production, a WSGI server like Gunicorn will import the 'app' object
    app.run()
