# 📧 gmailReader

A Python script to download emails from a specific sender within a given timeframe and save them to a plaintext file. The script uses the Gmail API to fetch email threads, extracts relevant metadata (subject, date, sender, and body), and saves the results in a structured format. It includes progress indicators (percentage complete, elapsed time, and email count) to provide real-time feedback during execution. This tool uses the Gmail API to fetch email threads, processes them to remove quoted text and unwanted signatures (e.g., Avast links), and saves the results to a file with a timestamped filename.

## ✨ Features

- **Sender-Specific Email Download**: Fetch emails from a specified sender (e.g., `asdf123@gmail.com`).
- **Customizable Date Range**: Filter emails by a specific timeframe (e.g., from March 1, 2025, to the present).
- **Plaintext Output**: Save emails in a clean plaintext format, removing quoted text, signatures, and footers.
- **Progress Indicators**: Real-time feedback with a percentage complete bar, elapsed time counter, and running email count.
- **Configurable Settings**: Easily adjust the sender, date range, and other settings at the top of the script.
- **Timestamped Filenames**: Output files are named with the sender, date range, and processing timestamp (e.g., `asdf123_gmail_com_from_20250301_to_now_processdttm_20250324_050421_emails.txt`).

## Prerequisites

- **Python 3.6+**: Ensure Python is installed on your system.
- **Google Cloud Project**: You need a Google Cloud project with the Gmail API enabled and OAuth 2.0 credentials set up.
- **Dependencies**: Install the required Python libraries listed in `requirements.txt`.

## Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/gmailReader.git
   cd gmailReader

---

## 🛠️ Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/gmailReader.git
   cd gmailReader
