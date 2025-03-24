import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email import policy
from email.parser import BytesParser

# Define the scopes (read-only access to Gmail)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Authenticate and build the Gmail API service."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            # creds = flow.run_local_server(port=0)
            creds = flow.run_local_server(port=8080)  # Specify a fixed port
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_emails_from_user(service, user_email, max_results=100):
    """Fetch emails from a specific user and return plaintext content."""
    try:
        # Search for emails from the specified user
        query = f'from:{user_email}'
        # Handle pagination to get all emails
        page_token = None
        all_messages = []
        while True:
            results = service.users().messages().list(userId='me', q=query, maxResults=max_results, pageToken=page_token).execute()
            messages = results.get('messages', [])
            all_messages.extend(messages)
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        email_texts = []
        if not all_messages:
            print(f"No emails found from {user_email}.")
            return email_texts

        for message in all_messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            # Decode the raw email content
            msg_data = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
            # Parse the email to extract plaintext
            msg = BytesParser(policy=policy.default).parsebytes(msg_data)
            plaintext_part = msg.get_body(preferencelist=('plain'))
            plaintext = plaintext_part.get_content().strip() if plaintext_part else "No plaintext content found."
            email_texts.append(plaintext)

        return email_texts

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def save_to_file(email_texts, user_email, filename='emails.txt'):
    """Save the email plaintext to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        for i, text in enumerate(email_texts, 1):
            f.write(f"Email {i} from {user_email}:\n{text}\n{'-'*50}\n")

if __name__ == '__main__':
    user_email = "asdf@gmail.com"  # Replace with the email address of the sender you want
    service = get_gmail_service()
    emails = get_emails_from_user(service, user_email, max_results=100)  # Adjust max_results as needed
    if emails:
        save_to_file(emails, user_email)
        print(f"Downloaded {len(emails)} emails and saved to 'emails.txt'.")
    else:
        print("No emails downloaded.")
