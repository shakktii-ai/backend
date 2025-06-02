# Flask Backend Deployment Guide

This guide provides step-by-step instructions for deploying your Python Flask backend to Render.com and connecting it with your Next.js frontend on Vercel.

## 1. Deploy the Flask Backend to Render.com

### Prerequisites
- A [Render.com](https://render.com) account (free tier available)
- Your code in a Git repository (GitHub, GitLab, etc.)

### Deployment Steps

1. **Log in to Render.com**
   - Create an account or log in at [render.com](https://render.com)

2. **Create a New Web Service**
   - Click "New +" and select "Web Service"
   - Connect your Git repository
   - Select the repository with your backend code

3. **Configure the Web Service**
   - Name: `invoice-processor-api` (or your preferred name)
   - Environment: `Python 3`
   - Region: Choose the region closest to your users
   - Branch: `main` (or your deployment branch)
   - Root Directory: `/backend` (if your repo contains both frontend and backend)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app.main:app`

4. **Set Environment Variables**
   - Add the following environment variables:
     - `ANTHROPIC_API_KEY`: Your Claude API key
     - `FLASK_ENV`: `production`
     - `FLASK_APP`: `app.main`
     - `UPLOAD_FOLDER`: `uploads`
     - `TEMP_FOLDER`: `temp`
     - `PROCESSED_FOLDER`: `processed`

5. **Advanced Settings**
   - Set auto-deploy to be triggered on your main branch
   - Select the appropriate instance type (Free tier is fine for testing)

6. **Create Web Service**
   - Click "Create Web Service"
   - Wait for the deployment to complete (this may take a few minutes)

7. **Verify Deployment**
   - Once deployed, visit the provided Render URL (e.g., `https://invoice-processor-api.onrender.com`)
   - You should see a success message or the API health check response

## 2. Update Frontend to Connect to the Deployed Backend

1. **Get Your Backend URL**
   - Copy the URL of your deployed backend (e.g., `https://invoice-processor-api.onrender.com`)

2. **Update Frontend Environment Variables**
   - Create or modify `.env.local` in your frontend directory:
     ```
     NEXT_PUBLIC_BACKEND_API_URL=https://your-backend-url.onrender.com
     ```

3. **Update API Call Endpoints (if needed)**
   - Make sure all API calls in your frontend code are using the environment variable

## 3. Deploy Frontend to Vercel

1. **Push Your Updated Frontend Code to GitHub**

2. **Log in to Vercel**
   - Create an account or log in at [vercel.com](https://vercel.com)

3. **Import Your Git Repository**
   - Click "Add New..." → "Project"
   - Select your repository
   - Configure:
     - Framework: Next.js
     - Root Directory: `/frontend` (if your repo has both frontend and backend)

4. **Environment Variables**
   - Add the following environment variables:
     - `NEXT_PUBLIC_BACKEND_API_URL`: Your Render backend URL
     - Any other required environment variables for your application

5. **Deploy**
   - Click "Deploy"
   - Wait for the deployment to complete

6. **Verify the Integration**
   - Test uploading invoices and processing them
   - Verify file downloads work correctly

## Troubleshooting

### CORS Issues
If you experience CORS issues:

1. Verify the CORS settings in your Flask backend:
   ```python
   CORS(app, resources={r"/api/*": {"origins": "*"}})
   ```

2. For production, restrict origins to your frontend domain:
   ```python
   CORS(app, resources={r"/api/*": {"origins": "https://your-frontend-domain.vercel.app"}})
   ```

### File Storage Issues
Render's free tier uses ephemeral storage, meaning files are not permanently stored. For production:

1. Use cloud storage solutions like AWS S3 or Google Cloud Storage
2. Update your backend code to use cloud storage for processed files

### API Key Security
Ensure your Claude API key is securely stored as an environment variable in Render.com and not hardcoded in your repository.

## Testing the Integration

1. Log in to your frontend application
2. Upload a sample invoice and chart of accounts
3. Process the invoice
4. Download the resulting file
5. Check logs in both Vercel and Render for any errors

## Production Considerations

- Set up a custom domain for your backend API
- Implement proper authentication for API endpoints
- Use a persistent database for storing file records and user data
- Set up monitoring and error tracking
- Consider scaling options for higher traffic
