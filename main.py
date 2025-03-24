import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email import policy
from email.parser import BytesParser
import html2text
from datetime import datetime

# Define the scopes (read-only access to Gmail)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():
    """Authenticate and build the Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def get_threads_involving_user(service, user_email, max_results=2000):
    """Fetch threads involving a specific user."""
    try:
        query = f'{user_email}'
        page_token = None
        all_threads = []
        while True:
            results = service.users().threads().list(userId='me', q=query, maxResults=max_results,
                                                     pageToken=page_token).execute()
            threads = results.get('threads', [])
            all_threads.extend(threads)
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return all_threads
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def clean_body_text(body):
    """Clean up the email body by preserving paragraph breaks and removing excessive spacing."""
    # Split into lines and strip whitespace
    lines = [line.strip() for line in body.split('\n')]
    # Remove excessive empty lines, but preserve single empty lines between paragraphs
    cleaned_lines = []
    previous_line_empty = False
    for line in lines:
        if line:
            cleaned_lines.append(line)
            previous_line_empty = False
        else:
            if not previous_line_empty:  # Only add one empty line between paragraphs
                cleaned_lines.append('')
                previous_line_empty = True
    # Join lines with single newlines
    cleaned_body = '\n'.join(cleaned_lines).strip()
    return cleaned_body


def remove_quoted_text(body):
    """Remove quoted text, signatures, and footers from the email body."""
    # Split into lines
    lines = body.split('\n')
    # Remove lines starting with '>' (quoted text)
    cleaned_lines = [line for line in lines if not line.strip().startswith('>')]
    # Remove lines starting with "On [date], [sender] wrote:"
    cleaned_lines = [line for line in cleaned_lines if not (line.strip().startswith('On ') and ' wrote:' in line)]
    # Remove everything after a signature marker (e.g., "-- ")
    signature_index = next((i for i, line in enumerate(cleaned_lines) if line.strip().startswith('--')),
                           len(cleaned_lines))
    cleaned_lines = cleaned_lines[:signature_index]
    return '\n'.join(cleaned_lines).strip()


def get_emails_in_thread(service, thread_id):
    """Fetch all emails in a thread and return metadata and plaintext content."""
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])

        email_data = []
        for msg in messages:
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
            date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'No Date')
            sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'Unknown Sender')

            raw_msg = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
            msg_data = base64.urlsafe_b64decode(raw_msg['raw'].encode('ASCII'))
            msg_parsed = BytesParser(policy=policy.default).parsebytes(msg_data)

            plaintext_part = msg_parsed.get_body(preferencelist=('plain'))
            if plaintext_part:
                body = plaintext_part.get_content().strip()
            else:
                html_part = msg_parsed.get_body(preferencelist=('html'))
                if html_part:
                    html_content = html_part.get_content().strip()
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.body_width = 0
                    body = h.handle(html_content).strip()
                else:
                    body = "No plaintext or HTML content found."

            # Remove quoted text and signatures
            body = remove_quoted_text(body)
            # Clean up spacing while preserving paragraphs
            body = clean_body_text(body)

            email_data.append({
                'subject': subject,
                'date': date,
                'sender': sender,
                'body': body
            })

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def save_to_file(email_data, user_email, filename):
    """Save the email metadata and plaintext to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        for i, email in enumerate(email_data, 1):
            f.write(f"Email {i}:\n")
            f.write(f"Subject: {email['subject']}\n")
            f.write(f"Date: {email['date']}\n")
            f.write(f"Sender: {email['sender']}\n")
            f.write(f"Body:\n{email['body']}\n")
            f.write(f"{'-' * 50}\n")


if __name__ == '__main__':
    # user_email = "premierpadsrentals@gmail.com" # works well
    # user_email = "chuchudragon@gmail.com" # works well: No threads found involving chuchudragon@gmail.com.
    # user_email = "chuchudragon22@gmail.com"  # works well: downloaded all emails
    user_email = "chuchudragon22@gmail.com"
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{sanitized_email}_{timestamp}_emails.txt"

    service = get_gmail_service()

    threads = get_threads_involving_user(service, user_email, max_results=2000)

    if not threads:
        print(f"No threads found involving {user_email}.")
    else:
        all_emails = []
        for thread in threads:
            thread_emails = get_emails_in_thread(service, thread['id'])
            all_emails.extend(thread_emails)

        if all_emails:
            save_to_file(all_emails, user_email, filename)
            print(f"Downloaded {len(all_emails)} emails and saved to '{filename}'.")
        else:
            print("No emails downloaded.")
