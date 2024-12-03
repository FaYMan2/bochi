from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse,HTMLResponse
from pydantic import BaseModel, HttpUrl, Field
import redis
import hashlib
from datetime import datetime,timedelta,timezone
import json


app = FastAPI()

REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
#REDIS_PWD: str = "password"

pageNotFound_page_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>404 - Page Not Found</title>
          <style>
            body {
              font-family: 'Arial', sans-serif;
              background-color: #f9f9f9;
              color: #333;
              margin: 0;
              padding: 0;
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              text-align: center;
            }
        
            .container {
              max-width: 600px;
              background: #ffffff;
              padding: 30px;
              border-radius: 10px;
              box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
        
            h1 {
              font-size: 3em;
              color: #e63946;
              margin-bottom: 10px;
            }
        
            p {
              font-size: 1.2em;
              margin-bottom: 20px;
            }
        
            a {
              display: inline-block;
              margin-top: 20px;
              padding: 10px 20px;
              font-size: 1em;
              color: #ffffff;
              background-color: #007bff;
              border: none;
              border-radius: 5px;
              text-decoration: none;
              transition: background-color 0.3s;
            }
        
            a:hover {
              background-color: #0056b3;
            }
          </style>
        </head>
        <body>
          <div class="container">
            <h1>404 - Error</h1>
            <p>Page Not Found! Please check the spelling of the URL or contact the owner for help.</p>
          </div>
        </body>
        </html>
"""

expired_page_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Link Expired</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              background-color: #f8f9fa;
              color: #343a40;
              text-align: center;
              padding: 50px;
            }
            .error-container {
              background-color: #ffffff;
              border: 1px solid #dee2e6;
              border-radius: 10px;
              padding: 30px;
              box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
              max-width: 500px;
              margin: auto;
            }
            h1 {
              font-size: 2em;
              color: #dc3545;
              margin-bottom: 20px;
            }
            p {
              font-size: 1.2em;
              margin-bottom: 15px;
            }
            a {
              text-decoration: none;
              color: #007bff;
            }
            a:hover {
              text-decoration: underline;
            }
          </style>
        </head>
        <body>
          <div class="error-container">
            <h1>ERROR: OOPS!</h1>
            <p>LINK HAS EXPIRED.</p>
            <p>If you need access, please contact the link creator.</p>
          </div>
        </body>
        </html>
        """


redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    #password=REDIS_PWD,
    decode_responses=True
)

DOMAIN = "https://short.ly"

class Link(BaseModel):
    link: HttpUrl
    expiry: int = Field(0, gt=-1, description="Expiration duration from creation time")
    created_at: datetime = Field(default_factory=datetime.now, description="The time when the link was created")

@app.post("/shorten")
async def shorten_link(link: Link):
    link_hash = hashlib.md5(str(link.link).encode()).hexdigest()[:6]  # Using first 6 characters for the short code
    if redis_client.exists(link_hash):
        short_url = f"{DOMAIN}/{link_hash}"
    else:
        redis_client.set(link_hash, json.dumps({"link" : str(link.link),
                                                "created_at" : str(link.created_at),
                                                "expiry" : link.expiry
                                                }))
        
        short_url = f"{DOMAIN}/{link_hash}"

    return {"original_link": link.link, "shortened_link": short_url}

@app.get("/{short_code}")
async def redirect(short_code: str):
    data = redis_client.get(short_code)
    if not data:
        return HTMLResponse(content=pageNotFound_page_content,status_code=404)
    original_link_data : Link = json.loads(data)
    current_time : datetime = datetime.now(timezone.utc)
    expiry_time : datetime = datetime.fromisoformat(original_link_data['created_at']) + timedelta(minutes=original_link_data['expiry'])
    if current_time > expiry_time:
        try:
            redis_client.delete(short_code)
            return HTMLResponse(content = expired_page_content ,status_code = 404)
        except Exception as e:
            print(f'error : {e}')
            return HTTPException(status_code=405,detail={"error" : str(e)})
    return RedirectResponse(url=original_link_data['link'])
