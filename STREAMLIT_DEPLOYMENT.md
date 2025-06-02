# Streamlit Deployment Guide

This guide explains how to deploy your Invoice Processor API using Streamlit Cloud.

## Prerequisites

- A GitHub account
- Your code pushed to a GitHub repository

## Deployment Steps

### 1. Prepare Your Repository

Make sure your repository has:
- `streamlit_app.py` (main application file)
- `requirements-streamlit.txt` (dependencies)
- `.streamlit/config.toml` (configuration)
- All necessary Python files (`perfect4.py`, `get_excel_sheets.py`, etc.)

### 2. Deploy to Streamlit Cloud

1. Go to [Streamlit Cloud](https://streamlit.io/cloud)
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository, branch, and the main file path (`streamlit_app.py`)
5. Click "Deploy"
6. Set the following secrets in the Streamlit Cloud dashboard:
   - `ANTHROPIC_API_KEY` = Your Claude API key

### 3. Alternative: Deploy to Render

1. Create a `render.yaml` file in your repository:
   ```yaml
   services:
     - type: web
       name: invoice-processor-api
       env: python
       buildCommand: pip install -r requirements-streamlit.txt
       startCommand: streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
       envVars:
         - key: ANTHROPIC_API_KEY
           sync: false
   ```

2. Sign up for [Render](https://render.com/)
3. Connect your GitHub repository
4. Deploy the web service using the `render.yaml` configuration
5. Add your environment variables in the Render dashboard

### 4. Important Considerations

- Make sure to create the required directories (`uploads`, `temp`, `processed`) in the deployed environment
- Configure CORS settings if needed for cross-origin requests
- Ensure your API key and other secrets are securely stored as environment variables
- For production use, consider implementing additional security measures

## After Deployment

Once deployed, your Streamlit app will provide:

1. A web UI for manual testing at your deployment URL
2. API endpoints for your frontend to use:
   - `https://your-deployment-url.streamlit.app/api/process-invoice`
   - `https://your-deployment-url.streamlit.app/api/get-sheets`
   - `https://your-deployment-url.streamlit.app/api/download-file/{filename}`

Note that for Streamlit Cloud deployments, you may need to add `/api` routes using a custom setup. Refer to the Streamlit documentation for more details.

## Troubleshooting

- Check the deployment logs if your app fails to start
- Verify that all environment variables are correctly set
- Ensure your dependencies are properly listed in `requirements-streamlit.txt`
- If files aren't being saved, check the permissions of your storage directories
