import os
import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

class YouTubeUploader:
    def __init__(self, client_secret_file, api_service_name="youtube", api_version="v3", scopes=None):
        if scopes is None:
            scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        
        self.client_secret_file = client_secret_file
        self.api_service_name = api_service_name
        self.api_version = api_version
        self.scopes = scopes
        self.credentials = None
        self.youtube = None
        self.token_file = 'token.json'
        self.authenticate()

    def authenticate(self):
        # OAuth 2.0 flow to get authenticated credentials
        if os.path.exists('token.json'):
            self.credentials = Credentials.from_authorized_user_file('token.json', self.scopes)
                
        # If no valid credentials, perform the OAuth flow
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                # Refresh the credentials if they're expired
                self.credentials.refresh(google.auth.transport.requests.Request())
            else:
                # OAuth 2.0 flow to get authenticated credentials for the first time
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_file, self.scopes
                )
                self.credentials = flow.run_local_server()

            # Save the credentials to a file for the next time
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
        
        # Build the YouTube service object
        self.youtube = googleapiclient.discovery.build(
            self.api_service_name, self.api_version, credentials=self.credentials
        )

    def upload_video(self, video_path, privacy_status="public", youtube_data=None):

        # Set up the video upload details
        body = {
            "snippet": youtube_data,
            "status": {
                "privacyStatus": privacy_status  # "public", "private", or "unlisted"
            }
        }

        # Upload the video file using the YouTube Data API
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        print("Upload complete!")
        print(f"Video ID: {response['id']}")
        # return the video url
        return f"https://www.youtube.com/watch?v={response['id']}"