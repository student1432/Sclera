# 🧪 Bubble Chat System - Testing Guide

## Quick Start Testing

### Step 1: Start the Server

```powershell
cd c:\Users\HP\Downloads\TEST1
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
 * Restarting with stat
 * Debugger is active!
```

### Step 2: Access the Chat

1. **Login** to your account at `http://localhost:5000`
2. **Navigate to a bubble** you're a member of
3. **Add `/chat`** to the URL:
   ```
   http://localhost:5000/bubble/{bubble_id}/chat
   ```

### Step 3: Test Basic Features

#### ✅ Send a Message
1. Type a message in the input box
2. Press Enter or click the send button
3. Message should appear instantly

#### ✅ Test Real-Time Sync
1. Open the same chat in a **second browser window** (or incognito)
2. Login as the same or different user
3. Send a message from one window
4. It should appear **instantly** in the other window

#### ✅ Test Typing Indicators
1. Open chat in two windows with different users
2. Start typing in one window
3. The other window should show "User is typing..."
4. Stop typing - indicator should disappear

#### ✅ Test Message Deletion
1. Send a message
2. Click the delete icon (trash can)
3. Confirm deletion
4. Message should disappear from all connected clients

#### ✅ Test Rate Limiting
1. Try sending 15 messages very quickly
2. After 10 messages, you should get:
   ```
   "Rate limit exceeded: Too many messages per minute"
   ```

---

## Advanced Testing

### Test Security Features

#### Input Sanitization
Try sending:
```
<script>alert('XSS')</script>
```
Expected: HTML tags are stripped, only text appears

#### Sensitive Data Redaction
Try sending:
```
My credit card is 1234-5678-9012-3456
```
Expected: Number is replaced with `[REDACTED-CARD]`

#### Long Messages
Try sending a message with 4001 characters
Expected: Error "Message exceeds maximum length"

---

## Multi-User Testing Scenarios

### Scenario 1: Group Chat
1. **User A** joins bubble chat
2. **User B** joins bubble chat
3. **User C** joins bubble chat
4. All users should see join notifications
5. Messages from any user appear for all users

### Scenario 2: Typing Indicators
1. **User A** starts typing
2. **User B** sees "User A is typing..."
3. **User A** stops typing (2 second timeout)
4. Indicator disappears for User B

### Scenario 3: Message Deletion
1. **User A** sends a message
2. **User A** deletes the message
3. **User B** sees the message disappear
4. **User C** (bubble creator) can delete anyone's messages

---

## Browser Console Testing

Open browser DevTools (F12) and check:

### WebSocket Connection
```javascript
// Should see in console:
"Connected to WebSocket"
```

### Real-Time Events
```javascript
// When someone joins:
{type: 'user_joined', uid: '...', name: '...'}

// When message is sent:
{type: 'new_message', bubble_id: '...', message: {...}}

// When someone types:
{type: 'user_typing', action: 'start', name: '...'}
```

---

## Performance Testing

### Load Test (Simple)
1. Open 5-10 browser tabs with the same chat
2. Send messages from different tabs
3. All tabs should update instantly
4. Check server logs for any errors

### Message History
1. Send 60+ messages
2. Refresh the page
3. Should load last 50 messages
4. Oldest messages should appear first

---

## Error Handling Testing

### Test 1: Invalid Bubble ID
Navigate to: `http://localhost:5000/bubble/invalid_id/chat`
Expected: Redirect with error "Bubble not found"

### Test 2: Non-Member Access
Try accessing a bubble you're not a member of
Expected: Redirect with error "You are not a member of this bubble"

### Test 3: Network Disconnection
1. Open chat
2. Disconnect from internet
3. Status should show "Offline"
4. Reconnect
5. Status should show "Online"

---

## Common Issues & Solutions

### Issue: WebSocket not connecting
**Symptoms**: Status shows "Connecting..." forever
**Solutions**:
1. Check server is running
2. Check browser console for errors
3. Verify Flask-SocketIO is installed: `pip list | grep Flask-SocketIO`
4. Try different browser

### Issue: Messages not appearing
**Symptoms**: Messages sent but don't show up
**Solutions**:
1. Check Firestore security rules
2. Verify user is bubble member
3. Check server logs: Look for errors in terminal
4. Check browser network tab for failed requests

### Issue: Rate limit errors
**Symptoms**: Can't send messages after a few attempts
**Solutions**:
1. Wait 1 minute and try again
2. For testing, adjust limits in `utils/security.py`
3. Clear rate limiter: Restart server

### Issue: Styling issues
**Symptoms**: Chat looks broken or unstyled
**Solutions**:
1. Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. Check browser console for CSS errors
3. Verify `styles.css` is loading

---

## Testing Checklist

### Basic Functionality
- [ ] Server starts without errors
- [ ] Can access chat page
- [ ] Can send messages
- [ ] Messages appear in real-time
- [ ] Can delete own messages
- [ ] Character counter works
- [ ] Message history loads

### Real-Time Features
- [ ] WebSocket connects successfully
- [ ] Typing indicators work
- [ ] Join/leave notifications appear
- [ ] Messages sync across multiple windows
- [ ] Online/offline status updates

### Security
- [ ] HTML is sanitized
- [ ] Rate limiting works
- [ ] Only members can access chat
- [ ] Only sender/creator can delete messages
- [ ] Sensitive data is redacted

### UI/UX
- [ ] Chat interface loads correctly
- [ ] Messages are properly formatted
- [ ] Timestamps display correctly
- [ ] Auto-scroll works
- [ ] Mobile responsive (test on phone)
- [ ] Animations are smooth

---

## Debug Mode

### Enable Verbose Logging

In `app.py`, the SocketIO is already configured with logging:
```python
socketio = SocketIO(app, logger=True, engineio_logger=False)
```

### Check Server Logs

Watch for these log messages:
```
User {uid} connected to WebSocket
User {uid} joined bubble room {bubble_id}
User {uid} left bubble room {bubble_id}
Send message error: {error}
```

### Browser Console Commands

Test WebSocket manually:
```javascript
// Check if socket is connected
socket.connected

// Manually emit event
socket.emit('join_bubble', {bubble_id: 'your_bubble_id'})

// Listen for events
socket.on('new_message', (data) => console.log('New message:', data))
```

---

## Success Criteria

Your chat system is working correctly if:

✅ Messages appear instantly (< 1 second latency)
✅ Multiple users can chat simultaneously
✅ Typing indicators show in real-time
✅ Message deletion works for all connected users
✅ Rate limiting prevents spam
✅ No errors in server logs or browser console
✅ UI is responsive and smooth

---

## Next Steps After Testing

Once everything works:

1. **Gather Feedback**: Have real users test the chat
2. **Monitor Performance**: Watch server logs for issues
3. **Add Features**: Implement todo lists, file sharing, etc.
4. **Optimize**: Add Redis for better scalability
5. **Deploy**: Move to production environment

---

## Need Help?

### Check These First:
1. Server logs (terminal where you ran `python app.py`)
2. Browser console (F12 → Console tab)
3. Network tab (F12 → Network tab)
4. Implementation summary: `.agent/IMPLEMENTATION_SUMMARY.md`

### Common Commands:
```powershell
# Restart server
Ctrl+C (stop)
python app.py (start)

# Check installed packages
pip list | grep -i socket

# View logs in real-time
# (Server logs appear in terminal automatically)
```

---

## 🎉 Happy Testing!

Your bubble chat system is ready to use. Start testing and enjoy real-time collaboration! 🚀

