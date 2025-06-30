import imaplib
import smtplib
import email
from email.message import EmailMessage
from openai import OpenAI
import os
from dotenv import load_dotenv
import csv
from datetime import datetime

load_dotenv()

# === Load credentials ===
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")
SMTP_SERVER = os.getenv("SMTP_SERVER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GMAIL_PIANO_LABEL = "PianoInquiries"
LOG_FILE = "email_responses_log.csv"

# === Connect to OpenAI ===
client = OpenAI(api_key=OPENAI_API_KEY)

# === School Info Prompt ===
SYSTEM_PROMPT = """
You are an assistant for a classical piano school.
Analyze the questions they ask. If the question is answerable by the following blob, just send them the blob (Marked by "START BLOB" and "END BLOB")
START BLOB), and make very small tweeks if there needs be.

START BLOB
All of our lessons are one-on-one, allowing each student to receive personalized instruction tailored to their individual needs. We do not offer group lessons, and sessions are typically held once a week.

Currently, we offer in-home lessons for students located in Irvine. For all other students, lessons take place at our Buena Park studio, located just in front of Cypress Community College.
Our Buena Park studio rates are as follows:
- 30-minute session: $35
- 45-minute session: $52.50
- 60-minute session: $70
For In-home lessons, the rates are as follows:
- 30-minute session: $40
- 45-minute session: $60
- 60-minute session: $80

The ideal lesson length is usually recommended after a trial lesson and can vary based on the student’s age and prior experience. For young beginners, we often suggest starting with 30-minute lessons to assess comfort level and focus. Lesson durations can always be adjusted over time.
To help determine if your child is ready for the program, we recommend checking the following:

✅   Can count numbers up to 5 independently
✅   Can recognize alphabet letters A through G
✅   Can write her name and numbers up to 5 without assistance

If she isn’t quite ready yet, we suggest encouraging her to listen to music regularly to help develop her sense of rhythm and interest in music.
Please let us know if you'd like more information or if you'd like to schedule a free trial lesson at our Buena Park studio.
END BLOB

If the question they ask is not entirely answered by the blob, Use the following facts when answering inquiries:
- All lessons are one-on-one and held weekly. No group lessons.
- In-home lessons are available only in Irvine. All other students come to the Buena Park studio near Cypress Community College.
- Buena Park studio rates: $35 (30min), $52.50 (45min), $70 (60min)
- In-home rates (Irvine only): $40 (30min), $60 (45min), $80 (60min)
- Trial lessons help determine appropriate length based on age and experience. Young beginners usually start with 30 minutes.
- Readiness checklist: Can count to 5, recognize letters A-G, and write name and numbers up to 5 without help.
- If not ready, recommend listening to music often to build rhythm.
- A free trial lesson is available at the Buena Park studio.
- If student already has prior experience, instead of a trial lesson, we offer a free evaluation/consultation for transfer students (students with prior experience). This allows us to better understand the student's current level and discuss their goals.

Answer inquiries based on this information in a friendly and professional tone, addressing them first as
"Mr" or "Mrs.", and answer the email as "Merit Academy of Music".
"""
def log_interaction(sender, question, reply):
    timestamp = datetime.now().isoformat()
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        if not file_exists:
            writer.writerow(['Timestamp', 'Sender', 'Question', 'Reply', 'Rating', 'Rating Reason'])  # headers
        writer.writerow([timestamp, sender, question.strip(), reply.strip()])

# === Read Unread Emails ===
def fetch_unread_emails() -> list:
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

    mail.select(f'{GMAIL_PIANO_LABEL}')  # Label name goes here
    result, data = mail.search(None, 'UNSEEN')
    email_ids = data[0].split()
    
    emails = []
    if not email_ids:
        return emails

    print(f"Fetched number of emails: {len(email_ids)}")
    for email_id in email_ids:
        result, data = mail.fetch(email_id, '(RFC822)')
        msg = email.message_from_bytes(data[0][1])
        sender = email.utils.parseaddr(msg['From'])[1]
        subject = msg['Subject']
        
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body += part.get_payload(decode=True).decode()
        else:
            body = msg.get_payload(decode=True).decode()
        
        emails.append((sender, subject, body))
    return emails

# === Generate AI Response ===
def generate_reply(message):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content.strip()

# === Send Email ===
def send_email(recipient, subject, reply_body):
    msg = EmailMessage()
    msg['Subject'] = f"Re: {subject}"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient
    msg.set_content(reply_body)

    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# === Main ===
def run_email_agent():
    emails = fetch_unread_emails()
    if not emails:
        print("No new messages.")
    else:
        for email in emails:
            sender, subject, body = email
            if sender and body:
                print(f"Replying to: {sender} | Subject: {subject}")
                print(f"Inquiry:\n{body}")
                print("\n -----------------------------------------\n\n")
                reply = generate_reply(body)

                # Log the interaction
                log_interaction(sender, body, reply)
                
                # send_email(sender, subject, reply)
                print(f"Reply:\n{reply}")

if __name__ == "__main__":
    run_email_agent()

