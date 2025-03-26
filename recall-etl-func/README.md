---


# Recall ETL Functions

The Recall ETL Functions module is a collection of Azure Functions that handle the Extract, Transform, Load (ETL) process for the Recall Alert System. This module is responsible for fetching recall data from the openFDA API, processing it, generating AI-enhanced summaries, and storing the results in Azure Table Storage and Azure AI Search.

---

## Data Pipeline

```
┌─────────────────┐    ┌─────────────────────────┐    ┌─────────────────┐
│                 │    │                         │    │                 │
│    OpenFDA      │───▶│  Extract Food Recalls   │───▶│  Split Into     │
│     API         │    │                         │    │   Batches       │
│                 │    │                         │    │                 │
└─────────────────┘    └─────────────────────────┘    └────────┬────────┘
                                                                │
                                                                ▼
┌─────────────────┐    ┌─────────────────────────┐    ┌─────────────────┐
│                 │    │                         │    │                 │
│  Update Azure   │◀───│   Store in Azure        │◀───│  Process with   │
│    AI Search    │    │    Table Storage        │    │  Azure OpenAI   │
│                 │    │                         │    │                 │
└─────────────────┘    └─────────────────────────┘    └─────────────────┘
```

---

## Key Features

- **Automated Data Collection**: Daily extraction from openFDA API at 11 PM
- **Batch Processing**: Divides recalls into manageable chunks for parallel processing
- **AI-Enhanced Summaries**: Generates consumer-friendly summaries using Azure OpenAI
- **Optimized Storage**: Stores processed data in Azure Table Storage
- **Search Indexing**: Updates Azure AI Search index for fast retrieval

---

## Azure Functions

### TriggerETLProcess
- **Type**: Timer Trigger
- **Schedule**: Daily at 11 PM
- **Purpose**: Initiates the ETL process and coordinates the execution flow

### ExtractOpenFDARecalls
- **Type**: Activity Function
- **Purpose**: Retrieves recall data from the openFDA API for the last 100 days

### SplitRecallBatches
- **Type**: Activity Function
- **Purpose**: Divides the recall data into manageable batches for parallel processing

### ProcessRecallBatch
- **Type**: Activity Function
- **Purpose**: Processes each batch of recalls and generates AI summaries

### StoreRecallData
- **Type**: Activity Function
- **Purpose**: Stores the processed data in Azure Table Storage

### UpdateSearchIndex
- **Type**: Activity Function
- **Purpose**: Updates the Azure AI Search index with the new recall data

---

## Azure OpenAI Integration

### Prompt Engineering
The system uses a template-based approach for generating consistent recall summaries:

```
Generate a consumer-friendly summary of this food recall information.
The summary should have the following sections:

1. Recall Overview - A brief summary including:
   - Product name and identifier
   - Recalling company and location
   - Specific reason for recall
   - Recall classification

2. Health Risks - Clear explanation of:
   - What the recall classification means for consumers
   - Specific health concerns related to the recall reason
   - Who might be most affected
   - Potential symptoms to watch for

...
```

### Summary Template
The AI-generated summaries follow a standardized format:
1. **Recall Overview**
2. **Product Details**
3. **Reason for Recall**
4. **Health Risks**
5. **Distribution & Affected Areas**
6. **Action Required**
7. **Additional Information**
8. **Reference**
9. **Contact Information**

---

## Local Development

### Setup
1. Clone the repository
2. Create a `local.settings.json` file with the required settings
3. Install Azure Functions Core Tools
4. Run `func start` to start the Function App locally

### Testing
To test the ETL process locally:
```bash
# Manually trigger the orchestrator function
curl -X POST http://localhost:7071/api/TriggerETLProcess -H "Content-Length: 0"

---

## License

MIT