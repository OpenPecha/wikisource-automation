# Wikisource Automation

<h1 align="center">
  <br>
  <a href="https://openpecha.org"><img src="https://avatars.githubusercontent.com/u/82142807?s=400&u=19e108a15566f3a1449bafb03b8dd706a72aebcd&v=4" alt="OpenPecha" width="150"></a>
  <br>
</h1>

## Wikisource Automation Toolkit

A comprehensive Python toolkit for automating Tibetan text processing and Wikisource content management workflows.

## Owner(s)

- [@ngawangtrinley](https://github.com/ngawangtrinley)
- [@mikkokotila](https://github.com/mikkokotila)
- [@evanyerburgh](https://github.com/evanyerburgh)

## Table of contents

<p align="center">
  <a href="#project-description">Project description</a> •
  <a href="#who-this-project-is-for">Who this project is for</a> •
  <a href="#project-dependencies">Project dependencies</a> •
  <a href="#project-structure">Project structure</a> •
  <a href="#setup-and-installation">Setup and installation</a> •
  <a href="#workflow-1-text-operations">Workflow 1: Text Operations</a> •
  <a href="#workflow-2-wikisource-upload">Workflow 2: Wikisource Upload</a> •
  <a href="#authentication-setup">Authentication setup</a> •
  <a href="#troubleshooting">Troubleshooting</a> •
  <a href="#contributing-guidelines">Contributing guidelines</a> •
  <a href="#how-to-get-help">How to get help</a> •
  <a href="#terms-of-use">Terms of use</a>
</p>
<hr>

## Project description

The **Wikisource Automation** provides two distinct automation workflows for processing Tibetan texts and managing Wikisource content:

1. **Text Operations Workflow**: Processes Tibetan texts, handles text splitting, uploads to Google Docs, and manages Google Sheets integration
2. **Wikisource Upload Workflow**: Automates the upload of OCR/text content to Wikisource pages with proper formatting and quality settings

This toolkit is specifically designed for handling Tibetan Buddhist texts with specialized text processing capabilities for Tibetan script markers, page references, and text variants.

## Who this project is for

This project is intended for:

- **Digital humanities scholars** working with Tibetan Buddhist texts
- **Wikisource contributors** who need to upload large volumes of Tibetan texts
- **Text processing specialists** handling Tibetan manuscript digitization
- **OpenPecha contributors** working on Buddhist text preservation projects

## Project dependencies

Before using this toolkit, ensure you have:

- **Python 3.8+**
- **Google Cloud Project** with APIs enabled (Drive, Docs, Sheets)
- **Wikisource account** with bot permissions (for Wikisource uploads)
- **Required credentials files** (see Authentication setup)

## Project structure

```
wikisource-automation/
├── src/wikisource/
│   ├── etext_upload.py              # Main Wikisource upload workflow
│   ├── text_operations/             # Text processing workflows
│   │   ├── text_splitter_txt/
│   │   │   └── kagyur_splitter.py   # Tibetan text splitter
│   │   └── GDocs_operations/
│   │       ├── upload_to_google_docs.py      # Upload texts to Google Docs
│   │       ├── drive_docs_link_retriever.py  # Retrieve Google Docs links
│   │       └── update_google_sheets.py       # Update sheets with URLs
│   ├── helper_function/
│   │   └── etext_UploadHelper_GSheet.py      # Google Sheets integration
│   └── utils/                       # Utility functions
├── tests/                           # Unit tests
├── requirements.txt                 # Python dependencies
├── pyproject.toml                  # Project configuration
├── oauth-credentials.json          # OAuth credentials (you need to add)
└── service-account-credentials.json # Service account (you need to add)
```

## Setup and installation

### 1. Clone and install dependencies

```bash
git clone https://github.com/OpenPecha/wikisource-automation.git
cd wikisource-automation
pip install -r requirements.txt
```

### 2. Set up authentication files

You need two credential files in the project root:

- `oauth-credentials.json` - OAuth client credentials for Google APIs
- `service-account-credentials.json` - Service account for Google Sheets access

See [Authentication setup](#authentication-setup) for detailed instructions.

### 3. Install the package

```bash
pip install -e .
```

## Workflow 1: Text Operations

The text operations workflow handles Tibetan text processing and Google services integration.

### Components:

#### A. Kagyur Text Splitter (`kagyur_splitter.py`)

Processes Tibetan texts with specialized handling for:

- **Section tokens**: `{D1}`, `{D1a}`, `{D4}` etc.
- **Page markers**: `[1a]`, `[2b]` etc.
- **Text variants**: `{བཅྭ་,བཅོ་}` (takes right side after comma)
- **Dotted markers**: `[1a.1]`, `[2b.4]` (removes entirely)

**Usage:**

```python
from src.wikisource.text_operations.text_splitter_txt.kagyur_splitter import LineByLineProcessor

# Set up input/output directories
input_dir = Path("data_text_operations/kagyur_text")
output_dir = Path("data_text_operations/kagyur_output")

# Process files
processor = LineByLineProcessor(input_dir, output_dir)
processor.process_all_files()
```

**Input format expected:**

```
{D1}དགེ་སློང་དག་སྔོན་བྱུང་བ་བཱ་རཱ་ཎ་སཱིའི་གྲོང་ཁྱེར་དུ།
[1a]རྒྱལ་པོ་ཚངས་སྦྱིན་ཞེས་བྱ་བ་རྒྱལ་སྲིད་བྱེད་དུ།
སྦྱང་བ་{བཅྭ་,བཅོ་}བརྒྱད་པོ་དག
{D2}གཞན་དུས་དང་། །བཞི་མདོ་དང་། སུམ་མདོ་རྣམས་སུ།
```

#### B. Google Docs Operations

**1. Upload to Google Docs (`upload_to_google_docs.py`)**

```python
from src.wikisource.text_operations.GDocs_operations.upload_to_google_docs import GoogleDocsUploader

uploader = GoogleDocsUploader('oauth-credentials.json')
uploader.upload_batch(start_id='D3999', end_id='D4464', delay=1.0)
```

**2. Retrieve Document Links (`drive_docs_link_retriever.py`)**

```python
from src.wikisource.text_operations.GDocs_operations.drive_docs_link_retriever import DriveDocumentLinker

linker = DriveDocumentLinker('oauth-credentials.json', 'your_folder_id')
filename_to_link = linker.get_all_document_links()
linker.save_to_json(filename_to_link)
```

**3. Update Google Sheets (`update_google_sheets.py`)**

```python
from src.wikisource.text_operations.GDocs_operations.update_google_sheets import GoogleSheetsUpdater

updater = GoogleSheetsUpdater('oauth-credentials.json')
updater.update_sheet_range(start_row=2106, end_row=2386)
```

### Text Operations Workflow Steps:

1. **Process Tibetan texts** with `kagyur_splitter.py`
2. **Upload processed texts** to Google Docs with `upload_to_google_docs.py`
3. **Retrieve document links** with `drive_docs_link_retriever.py`
4. **Update tracking sheets** with `update_google_sheets.py`

## Workflow 2: Wikisource Upload

The Wikisource upload workflow automates content upload to Wikisource pages.

### Key Features:

- Downloads text files from Google Drive/Docs via Google Sheets
- Parses page-by-page text format (`Page no: N`)
- Uploads to Wikisource with ProofreadPage formatting
- Handles caching and progress tracking
- Comprehensive logging and error handling

### Usage:

#### Method 1: Direct upload

```python
from src.wikisource.etext_upload import login_to_wikisource, upload_texts

site = login_to_wikisource()
upload_texts(site, "Index:YourIndexPage", "path/to/your/text.txt")
```

#### Method 2: Batch upload from CSV

```python
from src.wikisource.etext_upload import batch_upload_from_csv

batch_upload_from_csv("data/work_list.csv", "data/text/")
```

### Expected text file format:

```
Page no: 1
Your text content for page 1
More content for page 1

Page no: 2
Your text content for page 2
More content for page 2
```

### Configuration in `etext_upload.py`:

```python
# Update these variables in the main section:
sheet_id = "your_google_sheet_id"
range_rows = "YourSheet!G3:K8"  # Adjust range as needed
```

### Wikisource Upload Workflow Steps:

1. **Configure Google Sheet** with Wikisource index URLs and text file links
2. **Run the download process** to fetch text files and create CSV
3. **Review generated CSV** and text files
4. **Execute batch upload** to Wikisource

## Authentication setup

### 1. OAuth Credentials (`oauth-credentials.json`)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs: Drive API, Docs API, Sheets API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Desktop application"
6. Download the JSON file and rename to `oauth-credentials.json`
7. Place in project root directory

### 2. Service Account (`service-account-credentials.json`)

1. In Google Cloud Console, go to "Credentials"
2. "Create Credentials" → "Service account"
3. Create service account and download JSON key
4. Rename to `service-account-credentials.json`
5. Place in project root directory
6. Share your Google Sheets with the service account email

### 3. Pywikibot Configuration

For Wikisource uploads, configure pywikibot:

```bash
python -m pywikibot.scripts.generate_user_files
```

Follow prompts to set up your Wikisource bot account.

## Troubleshooting

<table>
  <tr>
   <td><strong>Issue</strong></td>
   <td><strong>Solution</strong></td>
  </tr>
  <tr>
   <td>Google API authentication errors</td>
   <td>Ensure credential files are in project root and APIs are enabled in Google Cloud Console</td>
  </tr>
  <tr>
   <td>Pywikibot login failures</td>
   <td>Run <code>python -m pywikibot.scripts.generate_user_files</code> and configure bot credentials</td>
  </tr>
  <tr>
   <td>Text processing errors with Tibetan characters</td>
   <td>Ensure files are saved with UTF-8 encoding</td>
  </tr>
  <tr>
   <td>Google Sheets permission denied</td>
   <td>Share sheets with service account email address</td>
  </tr>
  <tr>
   <td>Rate limiting errors</td>
   <td>Increase delay parameters in upload functions</td>
  </tr>
</table>

### Common File Paths:

- **Input texts**: `data_text_operations/kagyur_text/`
- **Output texts**: `data_text_operations/kagyur_output/`
- **Upload logs**: Project root (`upload_log.csv`)
- **Cache files**: `cache/` directory
- **Progress files**: Various `*_output/` directories

### Testing:

Run tests to verify functionality:

```bash
python -m pytest tests/
```

## Contributing guidelines

If you'd like to help out, check out our [contributing guidelines](/CONTRIBUTING.md).

## Additional documentation

For more information:

- [OpenPecha Documentation](https://openpecha.org)
- [Wikisource Help](https://wikisource.org/wiki/Help:Contents)
- [Google APIs Documentation](https://developers.google.com/docs)

## How to get help

- File an issue on GitHub
- Email us at openpecha[at]gmail.com
- Join our [Discord](https://discord.com/invite/7GFpPFSTeA)

## Terms of use

Wikisource Automation is licensed under the [MIT License](/LICENSE.md).
