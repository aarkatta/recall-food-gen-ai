
## Live Demo: [https://www.recalls.food](https://www.recalls.food){:target="_blank"}

# Recall Alert System

The Recall Alert System is a web application designed to provide users with real-time recall notifications for food products based on their location (ZIP code). The system integrates data from openFDA and enhances it with Azure AI services to deliver accurate and relevant recall alerts.

## Key Features

- **Landing Page**: Displays the latest nationwide recalls for the past 100 days. Each recall is summarized with a short overview and brand name. Clicking on a summary takes users to the detailed recall page.
- **Search Functionality**: Allows users to enter a ZIP code to find relevant recall information.
- **Recall Details Page**: Provides detailed recall data including product description, reason for recall, and affected locations.
- **Notifications**: Users can subscribe to receive alerts via email or SMS.
- **Data Enrichment**: Uses Azure AI to extract key phrases, classify recalls, and determine sentiment.

## Backend Technical Flow

### API Endpoints

1. **`/api/recent_recalls/` - Azure Function**
   - Fetches recalls for the last 100 days from Azure AI Search.
   - Returns recall overviews for the landing page.
   - Note: Does not use OpenFDA verification (only metadata is needed).

2. **`/api/recall_detail/{recall_number}` - Azure Function**
   - Checks the Redis cache for a stored summary.
   - Fetches real-time recall data from OpenFDA to verify recall status.
   - If the OpenFDA recall status matches the cached status, returns the stored summary.
   - If the status has changed, regenerates the summary using OpenAI, updates Redis, and returns the new summary.

## Frontend Technical Flow

- **Landing Page (`/api/recent_recalls/`)**:
  - Calls Azure AI Search to fetch recall overviews.
  - Displays recall title, recall firm, classification, and a summary preview.
  - Provides a link from each recall to the detailed page.

- **Recall Detailed Page (`/api/recall_detail/{recall_number}`)**:
  - Fetches full recall details from Redis.
  - Verifies the OpenFDA recall status; if changed, generates a new summary.
  - Displays the latest, up-to-date recall summary.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

