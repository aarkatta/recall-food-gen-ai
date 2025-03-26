---

# Recall API

The Recall API is an Azure Function-based backend service that retrieves and delivers food recall information to the front-end application. It serves as the intermediary between the user interface and the data storage services (Azure AI Search and Azure Table Storage).

---

## Features

- **Recent Recalls Endpoint**: Retrieves recent recall information for display on the landing page
- **Recall Detail Endpoint**: Provides detailed recall information for specific recall numbers
- **Intelligent Search**: Supports both ZIP code and product text searches with automatic query type detection
- **Geographic Search**: Handles location-based queries using geospatial data

---

## API Endpoints

### GET /api/recent_recalls

Fetches the most recent recalls from Azure AI Search for display on the landing page.

**Query Parameters:**
- `limit` (optional): Number of recalls to return (default: 10)
- `page` (optional): Page number for pagination (default: 1)

**Sample Response:**
```json
{
  "recalls": [
    {
      "recall_number": "F-0543-2025",
      "report_date": "20250219",
      "recalling_firm": "Chocolate Foods, Ltd.",
      "classification": "Class II",
      "summary_preview": "Chocolate Birthday Cake Granola Bars recalled due to potential metal pieces..."
    }
  ],
  "pagination": {
    "total_records": 243,
    "total_pages": 25,
    "current_page": 1,
    "records_per_page": 10
  }
}
```

### GET /api/recall_detail/{recall_number}

Retrieves the detailed AI-generated summary for a specific recall from Azure Table Storage.

**Path Parameters:**
- `recall_number`: The FDA recall identification number

**Sample Response:**
```json
{
  "recall_number": "F-0543-2025",
  "report_date": "20250219",
  "recalling_firm": "Natural ABC Foods, Ltd.",
  "classification": "Class II",
  "product_description": "Chocolate Birthday Cake Granola Bars",
  "reason_for_recall": "may contain metal pieces",
  "distribution_pattern": "nationwide",
  "summary": "**Recall Summary: Chocolate Birthday Cake Granola Bars**\n\n**1. Recall Overview**\n\nNatural ABC Foods, Ltd. has issued a voluntary recall..."
}
```

### GET /api/search

Intelligently identifies whether the query is a ZIP code or product text and returns matching recall information.

**Query Parameters:**
- `query`: ZIP code or product search text
- `limit` (optional): Number of recalls to return (default: 10)
- `page` (optional): Page number for pagination (default: 1)
- `sort` (optional): Sort order (options: date_desc, date_asc, relevance)

**Sample Response:**
```json
{
  "recalls": [
    {
      "recall_number": "F-0543-2025",
      "report_date": "20250219",
      "recalling_firm": "Natural ABC Foods, Ltd.",
      "classification": "Class II",
      "summary_preview": "Chocolate Birthday Cake Granola Bars recalled due to potential metal pieces...",
      "relevance_score": 0.95
    }
  ],
  "query_type": "product_search",
  "pagination": {
    "total_records": 12,
    "total_pages": 2,
    "current_page": 1,
    "records_per_page": 10
  }
}
```

---

## Technical Implementation

### Search Logic

- **ZIP Code Detection**:
  - Identifies if the query matches ZIP code format
  - Maps ZIP code to geographic area
  - Searches for recalls affecting that area

- **Product Text Search**:
  - Uses Azure AI Search for text-based queries
  - Implements fuzzy matching for typos
  - Ranks results by relevance score

---

## Deployment

### Prerequisites
- Azure Function App service
- Azure AI Search service with configured index
- Azure Table Storage with configured table

### Deployment Steps
1. Set up the Azure Resources
2. Configure application settings
3. Deploy using GitHub Actions or Azure CLI:
   func init
   func new --template "Http Trigger" --name APP_Name   
   func azure functionapp publish APP_Name

---

## Local Development

### Setup
1. Clone the repository
2. Create a `local.settings.json` file with the required settings
3. Install Azure Functions Core Tools
4. Run `func start` to start the Function App locally

---

## License

MIT