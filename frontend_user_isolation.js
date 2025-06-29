// frontend_user_isolation.js - Frontend integration for user-isolated data

class UserDataManager {
    constructor(baseURL, username) {
        this.baseURL = baseURL;
        this.username = username;
        this.cache = new Map();
        this.cacheTimeout = 30000; // 30 seconds
        this.isLoading = false; // To prevent multiple simultaneous fetches
    }

    // ==== API CALLS FOR USER-ISOLATED DATA ====
    
    async getUserDashboardData() {
        // Simple caching mechanism
        if (this.cache.has('dashboard') && !this.isLoading) {
            return this.cache.get('dashboard');
        }
        if (this.isLoading) {
            // If already loading, return current cached data or an empty object
            return this.cache.get('dashboard') || { error: "Data is currently loading." };
        }
        
        try {
            this.isLoading = true;
            console.log(`Fetching dashboard data for user: ${this.username}`);
            const response = await fetch(`${this.baseURL}/api/user/${this.username}/dashboard`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Dashboard API error: ${response.status} - ${errorData.message}`);
            }
            
            const data = await response.json();
            this.cache.set('dashboard', data);
            
            // Invalidate cache after timeout
            setTimeout(() => {
                this.cache.delete('dashboard');
                console.log(`Dashboard data cache for ${this.username} cleared.`);
            }, this.cacheTimeout);
            
            return data;
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            // Return a structured error object so GUI can display it
            return { error: 'Failed to load dashboard data', details: error.message };
        } finally {
            this.isLoading = false;
        }
    }
    
    async getUserChatHistory(limit = 50) {
        try {
            console.log(`Fetching chat history for user: ${this.username}, limit: ${limit}`);
            const response = await fetch(`${this.baseURL}/api/user/${this.username}/chat_history?limit=${limit}`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Chat history API error: ${response.status} - ${errorData.message}`);
            }
            
            const data = await response.json();
            return data.chat_history || [];
        } catch (error) {
            console.error('Failed to load chat history:', error);
            return []; // Return empty array on error
        }
    }
    
    async getUserStats() {
        try {
            console.log(`Fetching user stats for user: ${this.username}`);
            const response = await fetch(`${this.baseURL}/api/user/${this.username}/stats`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Stats API error: ${response.status} - ${errorData.message}`);
            }
            
            const data = await response.json();
            return data; // This should directly return the stats object
        } catch (error) {
            console.error('Failed to load user stats:', error);
            return { error: 'Failed to load user stats', details: error.message }; // Return error object
        }
    }

    async updateUserFunnelProgress(funnelState, platform) {
        try {
            console.log(`Updating funnel progress for ${this.username}: state=${funnelState}, platform=${platform}`);
            const response = await fetch(`${this.baseURL}/api/user/${this.username}/update_state`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ funnel_state: funnelState, platform: platform })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Update state API error: ${response.status} - ${errorData.message}`);
            }
            const data = await response.json();
            console.log('Funnel progress update response:', data);
            // Optionally, clear dashboard cache to force refresh on next fetch
            this.cache.delete('dashboard'); 
            return data;
        } catch (error) {
            console.error('Failed to update funnel progress:', error);
            return { status: "error", message: "Failed to update funnel progress", details: error.message };
        }
    }

    async uploadUserImage(file, label = "User Uploaded Image") {
        try {
            console.log(`Uploading image for user: ${this.username}, label: ${label}`);
            const formData = new FormData();
            formData.append('user_id', this.username);
            formData.append('file', file);
            formData.append('label', label);

            const response = await fetch(`${this.baseURL}/upload_user_image`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Image upload API error: ${response.status} - ${errorData.error || errorData.message}`);
            }

            const data = await response.json();
            console.log('Image upload response:', data);
            this.cache.delete('dashboard'); // Invalidate dashboard cache
            return data;
        } catch (error) {
            console.error('Failed to upload image:', error);
            return { error: 'Failed to upload image', details: error.message };
        }
    }

    async clearUserAIMemory() {
        try {
            console.log(`Clearing AI memory for user: ${this.username}`);
            const response = await fetch(`${this.baseURL}/clear_user_ai_memory`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: this.username })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Clear AI memory API error: ${response.status} - ${errorData.message}`);
            }

            const data = await response.json();
            console.log('Clear AI memory response:', data);
            this.cache.clear(); // Clear all cache related to this user
            return data;
        } catch (error) {
            console.error('Failed to clear AI memory:', error);
            return { error: 'Failed to clear AI memory', details: error.message };
        }
    }

    async sendManualMessage(messageContent, platform, filePath = null) {
        try {
            console.log(`Sending manual message for ${this.username} on ${platform}. Message: ${messageContent || filePath}`);
            const payload = {
                user_id: this.username,
                platform: platform,
                message: messageContent,
                file_path: filePath
            };

            const response = await fetch(`${this.baseURL}/send_manual_message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Send manual message API error: ${response.status} - ${errorData.message}`);
            }
            const data = await response.json();
            console.log('Send manual message response:', data);
            return data;
        } catch (error) {
            console.error('Failed to send manual message:', error);
            return { status: "error", message: "Failed to send manual message", details: error.message };
        }
    }

    async getManualMessages() {
        try {
            console.log(`Fetching manual messages for user: ${this.username}`);
            const response = await fetch(`${this.baseURL}/get_manual_messages_for_user/${this.username}`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
                throw new Error(`Get manual messages API error: ${response.status} - ${errorData.message}`);
            }
            
            const data = await response.json();
            return data.messages || [];
        } catch (error) {
            console.error('Failed to load manual messages:', error);
            return [];
        }
    }
}

// Example usage in your GUI (e.g., in dashboard.html or a main JS file)
// Assuming you get the username after login:

/*
// In your login success callback:
async function handleLoginSuccess(userData) {
    const username = userData.username; // Or wherever you store the logged-in username
    const API_BASE_URL = "http://192.168.12.34:5000"; // Ensure this matches your Flask API URL
    const userManager = new UserDataManager(API_BASE_URL, username);

    // Fetch and display dashboard data
    const dashboardData = await userManager.getUserDashboardData();
    console.log("Dashboard Data:", dashboardData);
    // Update your GUI elements with dashboardData.stats, dashboardData.recent_activity, etc.

    // Example of sending a manual message
    // const sendResult = await userManager.sendManualMessage("Hello from GUI!", "web");
    // console.log(sendResult);
}
*/