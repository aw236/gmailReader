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
import time
from tqdm import tqdm

# ------------------- Configuration Variables -------------------
USER_EMAIL = "asdf123@gmail.com"
START_DATETIME = datetime(2024, 3, 29, 0, 0, 0)
END_DATETIME = "now"
MAX_RESULTS = 2000
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# ---------------------------------------------------------------


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


def datetime_to_epoch(dt):
    """Convert a datetime object to epoch timestamp."""
    return int(dt.timestamp())


def format_elapsed_time(seconds):
    """Format elapsed time in seconds to a string (e.g., 'MM:SS')."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"


def get_threads_involving_user(service, user_email, max_results=MAX_RESULTS, start_datetime=None, end_datetime=None):
    """Fetch threads involving a specific user within a date range."""
    try:
        query = f'{user_email}'
        if start_datetime:
            start_epoch = datetime_to_epoch(start_datetime)
            query += f' after:{start_epoch}'
        if end_datetime:
            if end_datetime == "now":
                end_epoch = datetime_to_epoch(datetime.now())
            else:
                end_epoch = datetime_to_epoch(end_datetime)
            query += f' before:{end_epoch}'

        page_token = None
        total_threads = 0
        while True:
            results = service.users().threads().list(userId='me', q=query, maxResults=max_results,
                                                     pageToken=page_token).execute()
            threads = results.get('threads', [])
            total_threads += len(threads)
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        page_token = None
        all_threads = []
        with tqdm(total=total_threads, desc="Fetching threads", unit="thread") as pbar:
            while True:
                results = service.users().threads().list(userId='me', q=query, maxResults=max_results,
                                                         pageToken=page_token).execute()
                threads = results.get('threads', [])
                all_threads.extend(threads)
                pbar.update(len(threads))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
        return all_threads
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def clean_body_text(body):
    """Clean up the email body by preserving paragraph breaks and removing excessive spacing."""
    lines = [line.strip() for line in body.split('\n')]
    cleaned_lines = []
    previous_line_empty = False
    for line in lines:
        if line:
            cleaned_lines.append(line)
            previous_line_empty = False
        else:
            if not previous_line_empty:
                cleaned_lines.append('')
                previous_line_empty = True
    cleaned_body = '\n'.join(cleaned_lines).strip()
    return cleaned_body


def remove_quoted_text(body):
    """Remove quoted text, signatures, footers, and Avast links from the email body."""
    lines = body.split('\n')
    cleaned_lines = []
    for line in lines:
        if 'www.avast.com' in line.lower():
            continue
        if '<#' in line and '#>' in line:
            continue
        if line.strip().startswith('>'):
            continue
        if line.strip().startswith('On ') and ' wrote:' in line:
            continue
        cleaned_lines.append(line)

    signature_index = next((i for i, line in enumerate(cleaned_lines) if line.strip().startswith('--')),
                           len(cleaned_lines))
    cleaned_lines = cleaned_lines[:signature_index]
    return '\n'.join(cleaned_lines).strip()


def count_attachments(payload):
    """Count the number of attachments in the email payload."""
    attachment_count = 0
    if 'parts' in payload:
        for part in payload.get('parts', []):
            # Check if the part has a filename and is not a text/plain or text/html part
            if (part.get('filename') and part.get('mimeType') not in ['text/plain', 'text/html']):
                attachment_count += 1
            # Recursively check nested parts (e.g., multipart/mixed)
            attachment_count += count_attachments(part)
    return attachment_count


def get_emails_in_thread(service, thread_id, email_counter, start_time, pbar):
    """Fetch all emails in a thread and return metadata, plaintext content, and attachment count."""
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])

        email_data = []
        for msg in messages:
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
            date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'No Date')
            sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'Unknown Sender')
            recipient = next((header['value'] for header in headers if header['name'].lower() == 'to'), 'Unknown Recipient')

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

            body = remove_quoted_text(body)
            body = clean_body_text(body)

            # Count attachments in the payload
            attachment_count = count_attachments(msg['payload'])

            email_data.append({
                'subject': subject,
                'date': date,
                'sender': sender,
                'recipient': recipient,
                'body': body,
                'attachments': attachment_count  # Added attachment count
            })

            email_counter[0] += 1
            elapsed_time = time.time() - start_time
            pbar.set_postfix({
                'Emails': email_counter[0],
                'Elapsed': format_elapsed_time(elapsed_time)
            })
            pbar.update(1)

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def save_to_file(email_data, user_email, filename):
    """Save the email metadata, plaintext, and attachment count to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        for i, email in enumerate(email_data, 1):
            f.write(f"Email {i}:\n")
            f.write(f"Subject: {email['subject']}\n")
            f.write(f"Date: {email['date']}\n")
            f.write(f"Sender: {email['sender']}\n")
            f.write(f"Recipient: {email['recipient']}\n")
            f.write(f"Attachments: {email['attachments']}\n")  # Added attachment count
            f.write(f"Body:\n{email['body']}\n")
            f.write(f"{'-' * 50}\n")


if __name__ == '__main__':
    user_email = USER_EMAIL
    start_datetime = START_DATETIME
    end_datetime = END_DATETIME
    max_results = MAX_RESULTS

    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    if start_datetime:
        start_date_str = start_datetime.strftime('%Y%m%d')
    else:
        start_date_str = "all"
    if end_datetime == "now":
        end_datetime_obj = datetime.now()
        end_date_str = "now"
    elif end_datetime:
        end_datetime_obj = end_datetime
        end_date_str = end_datetime.strftime('%Y%m%d')
    else:
        end_datetime_obj = datetime.now()
        end_date_str = "now"
    process_dttm = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{sanitized_email}_from_{start_date_str}_to_{end_date_str}_processdttm_{process_dttm}_emails.txt"

    start_time = time.time()

    service = get_gmail_service()

    threads = get_threads_involving_user(
        service,
        user_email,
        max_results=max_results,
        start_datetime=start_datetime,
        end_datetime=end_datetime
    )

    if not threads:
        print(f"No threads found involving {user_email} within the specified date range.")
    else:
        total_emails = 0
        for thread in threads:
            thread_data = service.users().threads().get(userId='me', id=thread['id']).execute()
            total_emails += len(thread_data.get('messages', []))

        all_emails = []
        email_counter = [0]
        with tqdm(total=total_emails, desc="Processing emails", unit="email") as pbar:
            for thread in threads:
                thread_emails = get_emails_in_thread(service, thread['id'], email_counter, start_time, pbar)
                all_emails.extend(thread_emails)

        if all_emails:
            save_to_file(all_emails, user_email, filename)
            elapsed_time = time.time() - start_time
            print(f"Downloaded {len(all_emails)} emails and saved to '{filename}'.")
            print(f"Total elapsed time: {format_elapsed_time(elapsed_time)}")
        else:
            print("No emails downloaded.")
