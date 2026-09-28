# app.py - Azure App Service 및 WSGI 진입점
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
