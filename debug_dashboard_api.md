# Debug Dashboard API Calls

## Step 1: Open Browser DevTools
1. Press `F12` to open DevTools
2. Go to the **Network** tab
3. Check "Preserve log" checkbox
4. Clear the network log (trash icon)

## Step 2: Refresh the Dashboard
1. Click the "Refresh" button on the Dashboard
2. Watch the Network tab for API calls

## Step 3: Check API Calls
Look for these API calls (they should appear in the Network tab):

### Expected API Calls:
1. `/api/v1/conport/custom-data?category=wbs_meta&...`
2. `/api/v1/conport/dashboard?...`
3. `/api/v1/conport/progress?limit=500&...`
4. `/api/v1/conport/progress?description_prefix=Phase&limit=200&...` ← **This should fetch your phases**
5. `/api/v1/conport/progress?description_prefix=[P&limit=200&...`

### What to Check:
For the call with `description_prefix=Phase`:
1. Click on it in the Network tab
2. Go to the "Response" tab
3. Look for your phases (IDs 94-100) in the JSON response

## Step 4: Check Console for Errors
1. Go to the **Console** tab in DevTools
2. Look for any red error messages
3. Copy any errors you see

## Step 5: Check What URL is Being Used
In the Network tab, check the full URL of the API calls:
- Are they going to `localhost:8000`? (mindscape-ai API)
- Are they going to `localhost:8002`? (model-proxy API - won't work!)
- Do they have `?app_id=model-proxy` parameter?

## Common Issues:

### Issue 1: Wrong API Server
If calls are going to `localhost:8002`, the ConPort API doesn't exist there.
**Fix**: Make sure you're accessing the web UI through the mindscape-ai server.

### Issue 2: Missing app_id Parameter
If the URL doesn't have `?app_id=model-proxy`, it's looking at the wrong database.
**Fix**: Add `?app_id=model-proxy` to the URL manually.

### Issue 3: API Returns Empty Results
If the API call succeeds but returns 0 entries, the app_id isn't registered.
**Fix**: Check the Supabase app registry or MINDSCAPE_APP_ROOTS env var.

## Quick Test URL
Try accessing this URL directly in your browser:
```
http://localhost:8000/api/v1/conport/progress?app_id=model-proxy&description_prefix=Phase&limit=200
```

You should see a JSON response with your 7 LiteLLM phases (IDs 94-100).
