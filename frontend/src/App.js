import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = React.createContext();

const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API}/me`);
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/login`, { email, password });
      const { token: newToken, user: userData } = response.data;
      
      localStorage.setItem('token', newToken);
      setToken(newToken);
      setUser(userData);
      axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Login failed' };
    }
  };

  const register = async (email, password, name) => {
    try {
      const response = await axios.post(`${API}/register`, { email, password, name });
      const { token: newToken, user: userData } = response.data;
      
      localStorage.setItem('token', newToken);
      setToken(newToken);
      setUser(userData);
      axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Registration failed' };
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    delete axios.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

// Login/Register Component
const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const result = isLogin 
      ? await login(email, password)
      : await register(email, password, name);

    if (!result.success) {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-rose-100 to-pink-200 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Que Bella</h1>
          <p className="text-gray-600">Your AI-powered couples journal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none transition"
              required
            />
          </div>

          {!isLogin && (
            <div>
              <input
                type="text"
                placeholder="Your Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none transition"
                required
              />
            </div>
          )}

          <div>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none transition"
              required
            />
          </div>

          {error && (
            <div className="text-red-500 text-sm text-center">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-rose-500 text-white py-3 rounded-lg font-semibold hover:bg-rose-600 transition disabled:opacity-50"
          >
            {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div className="text-center mt-6">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-rose-500 hover:text-rose-600 transition"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
};

// Main App Component
const JournalApp = () => {
  const { user, logout } = useAuth();
  const [currentView, setCurrentView] = useState('journal');
  const [journalEntry, setJournalEntry] = useState('');
  const [selectedMood, setSelectedMood] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [calendarData, setCalendarData] = useState([]);
  const [stats, setStats] = useState({});
  const [inviteCode, setInviteCode] = useState('');
  const [showInviteModal, setShowInviteModal] = useState(false);

  const moods = [
    { emoji: '😊', name: 'Happy' },
    { emoji: '😔', name: 'Sad' },
    { emoji: '😍', name: 'Loved' },
    { emoji: '😴', name: 'Tired' },
    { emoji: '😄', name: 'Excited' },
    { emoji: '😌', name: 'Peaceful' },
    { emoji: '😤', name: 'Frustrated' },
    { emoji: '🥰', name: 'Grateful' }
  ];

  useEffect(() => {
    fetchStats();
    fetchCalendarData();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const fetchCalendarData = async () => {
    try {
      const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM
      const response = await axios.get(`${API}/calendar/${currentMonth}`);
      setCalendarData(response.data);
    } catch (error) {
      console.error('Failed to fetch calendar data:', error);
    }
  };

  const saveJournalEntry = async () => {
    if (!journalEntry.trim()) return;

    try {
      await axios.post(`${API}/journal`, {
        content: journalEntry,
        date: selectedDate,
        mood: selectedMood
      });

      if (selectedMood) {
        await axios.post(`${API}/mood`, {
          mood: selectedMood,
          date: selectedDate
        });
      }

      setJournalEntry('');
      setSelectedMood('');
      fetchStats();
      fetchCalendarData();
      alert('Entry saved successfully!');
    } catch (error) {
      console.error('Failed to save entry:', error);
      alert('Failed to save entry');
    }
  };

  const generateReflection = async (date) => {
    try {
      const response = await axios.post(`${API}/generate-reflection/${date}`);
      alert('AI Reflection generated successfully!');
      fetchCalendarData();
    } catch (error) {
      console.error('Failed to generate reflection:', error);
      alert(error.response?.data?.detail || 'Failed to generate reflection');
    }
  };

  const invitePartner = async () => {
    if (!inviteCode.trim()) return;

    try {
      const response = await axios.post(`${API}/invite-partner`, {
        invite_code: inviteCode
      });
      alert(`Partner linked successfully! Welcome ${response.data.partner_name}!`);
      setInviteCode('');
      setShowInviteModal(false);
      fetchStats();
      window.location.reload();
    } catch (error) {
      console.error('Failed to invite partner:', error);
      alert(error.response?.data?.detail || 'Failed to invite partner');
    }
  };

  const getTodayEntry = () => {
    const today = new Date().toISOString().split('T')[0];
    return calendarData.find(day => day.date === today);
  };

  const todayEntry = getTodayEntry();

  return (
    <div className="min-h-screen bg-gradient-to-br from-rose-50 to-pink-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Que Bella</h1>
            <p className="text-sm text-gray-600">Welcome back, {user?.name}!</p>
          </div>
          <div className="flex items-center space-x-4">
            {user?.invite_code && (
              <div className="text-sm">
                <span className="text-gray-600">Your invite code: </span>
                <span className="font-mono bg-gray-100 px-2 py-1 rounded">{user.invite_code}</span>
              </div>
            )}
            <button
              onClick={() => setShowInviteModal(true)}
              className="bg-rose-500 text-white px-4 py-2 rounded-lg hover:bg-rose-600 transition"
            >
              {stats.has_partner ? 'Partner Linked' : 'Invite Partner'}
            </button>
            <button
              onClick={logout}
              className="text-gray-600 hover:text-gray-800 transition"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Navigation */}
        <div className="flex space-x-4 mb-8">
          <button
            onClick={() => setCurrentView('journal')}
            className={`px-6 py-2 rounded-lg font-medium transition ${
              currentView === 'journal' 
                ? 'bg-rose-500 text-white' 
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Journal
          </button>
          <button
            onClick={() => setCurrentView('calendar')}
            className={`px-6 py-2 rounded-lg font-medium transition ${
              currentView === 'calendar' 
                ? 'bg-rose-500 text-white' 
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Calendar
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">Total Entries</h3>
            <p className="text-3xl font-bold text-rose-500">{stats.total_entries || 0}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">Shared Days</h3>
            <p className="text-3xl font-bold text-rose-500">{stats.shared_days || 0}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">AI Reflections</h3>
            <p className="text-3xl font-bold text-rose-500">{stats.reflections || 0}</p>
          </div>
        </div>

        {/* Journal View */}
        {currentView === 'journal' && (
          <div className="space-y-6">
            {/* Today's Entry Preview */}
            {todayEntry && (
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Today's Journal</h3>
                {todayEntry.my_entry ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-rose-50 rounded-lg">
                      <h4 className="font-medium text-gray-800 mb-2">Your Entry</h4>
                      <p className="text-gray-700">{todayEntry.my_entry.content}</p>
                      {todayEntry.my_mood && (
                        <p className="mt-2 text-sm text-gray-600">Mood: {todayEntry.my_mood.mood}</p>
                      )}
                    </div>
                    
                    {todayEntry.partner_entry && (
                      <div className="p-4 bg-blue-50 rounded-lg">
                        <h4 className="font-medium text-gray-800 mb-2">Partner's Entry</h4>
                        <p className="text-gray-700">{todayEntry.partner_entry.content}</p>
                        {todayEntry.partner_mood && (
                          <p className="mt-2 text-sm text-gray-600">Mood: {todayEntry.partner_mood.mood}</p>
                        )}
                      </div>
                    )}

                    {todayEntry.reflection ? (
                      <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                        <h4 className="font-medium text-gray-800 mb-2 flex items-center">
                          ✨ AI Reflection
                        </h4>
                        <p className="text-gray-700 italic">"{todayEntry.reflection.reflection}"</p>
                      </div>
                    ) : todayEntry.partner_entry && (
                      <button
                        onClick={() => generateReflection(todayEntry.date)}
                        className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white py-3 rounded-lg font-medium hover:from-purple-600 hover:to-pink-600 transition"
                      >
                        ✨ Generate AI Reflection
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-gray-500">No entry for today yet.</p>
                )}
              </div>
            )}

            {/* New Entry Form */}
            <div className="bg-white rounded-xl p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Write Your Journal Entry</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Date</label>
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">How are you feeling?</label>
                  <div className="grid grid-cols-4 gap-2">
                    {moods.map((mood) => (
                      <button
                        key={mood.name}
                        onClick={() => setSelectedMood(mood.name)}
                        className={`p-3 rounded-lg border-2 transition ${
                          selectedMood === mood.name
                            ? 'border-rose-400 bg-rose-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="text-2xl mb-1">{mood.emoji}</div>
                        <div className="text-xs text-gray-600">{mood.name}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Your journal entry</label>
                  <textarea
                    value={journalEntry}
                    onChange={(e) => setJournalEntry(e.target.value)}
                    placeholder="What's on your mind today? Share your thoughts, feelings, and experiences..."
                    className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none resize-none"
                  />
                </div>

                <button
                  onClick={saveJournalEntry}
                  disabled={!journalEntry.trim()}
                  className="w-full bg-rose-500 text-white py-3 rounded-lg font-medium hover:bg-rose-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save Entry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Calendar View */}
        {currentView === 'calendar' && (
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-6">Your Shared Journey</h3>
            <div className="space-y-4">
              {calendarData.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No entries yet. Start writing your first journal entry!</p>
              ) : (
                calendarData
                  .sort((a, b) => new Date(b.date) - new Date(a.date))
                  .map((day) => (
                    <div key={day.date} className="border border-gray-200 rounded-lg p-4 space-y-3">
                      <div className="flex justify-between items-center">
                        <h4 className="font-medium text-gray-800">
                          {new Date(day.date + 'T00:00:00').toLocaleDateString('en-US', { 
                            weekday: 'long', 
                            year: 'numeric', 
                            month: 'long', 
                            day: 'numeric' 
                          })}
                        </h4>
                        {day.my_entry && day.partner_entry && !day.reflection && (
                          <button
                            onClick={() => generateReflection(day.date)}
                            className="text-sm bg-gradient-to-r from-purple-500 to-pink-500 text-white px-3 py-1 rounded-full hover:from-purple-600 hover:to-pink-600 transition"
                          >
                            ✨ Generate Reflection
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {day.my_entry && (
                          <div className="p-3 bg-rose-50 rounded-lg">
                            <h5 className="text-sm font-medium text-gray-800 mb-1">Your Entry</h5>
                            <p className="text-sm text-gray-700">{day.my_entry.content}</p>
                            {day.my_mood && (
                              <p className="text-xs text-gray-600 mt-1">Mood: {day.my_mood.mood}</p>
                            )}
                          </div>
                        )}

                        {day.partner_entry && (
                          <div className="p-3 bg-blue-50 rounded-lg">
                            <h5 className="text-sm font-medium text-gray-800 mb-1">Partner's Entry</h5>
                            <p className="text-sm text-gray-700">{day.partner_entry.content}</p>
                            {day.partner_mood && (
                              <p className="text-xs text-gray-600 mt-1">Mood: {day.partner_mood.mood}</p>
                            )}
                          </div>
                        )}
                      </div>

                      {day.reflection && (
                        <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                          <h5 className="text-sm font-medium text-gray-800 mb-2 flex items-center">
                            ✨ AI Reflection
                          </h5>
                          <p className="text-sm text-gray-700 italic">"{day.reflection.reflection}"</p>
                        </div>
                      )}
                    </div>
                  ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Partner Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-xl font-bold text-gray-800 mb-4">
              {stats.has_partner ? 'Partner Already Linked' : 'Invite Your Partner'}
            </h3>
            
            {stats.has_partner ? (
              <div className="text-center">
                <p className="text-gray-600 mb-4">You're already connected with your partner!</p>
                <button
                  onClick={() => setShowInviteModal(false)}
                  className="bg-rose-500 text-white px-6 py-2 rounded-lg hover:bg-rose-600 transition"
                >
                  Close
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <p className="text-gray-600 mb-3">Share your invite code with your partner:</p>
                  <div className="p-3 bg-gray-100 rounded-lg text-center">
                    <span className="font-mono text-lg">{user?.invite_code}</span>
                  </div>
                </div>
                
                <div className="text-center text-gray-500">or</div>
                
                <div>
                  <p className="text-gray-600 mb-2">Enter your partner's invite code:</p>
                  <input
                    type="text"
                    placeholder="Enter invite code"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-400 focus:border-transparent outline-none"
                  />
                </div>

                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowInviteModal(false)}
                    className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-lg hover:bg-gray-400 transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={invitePartner}
                    disabled={!inviteCode.trim()}
                    className="flex-1 bg-rose-500 text-white py-2 rounded-lg hover:bg-rose-600 transition disabled:opacity-50"
                  >
                    Link Partner
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Main App Component
const App = () => {
  return (
    <AuthProvider>
      <div className="App">
        <AuthFlow />
      </div>
    </AuthProvider>
  );
};

const AuthFlow = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-rose-100 to-pink-200 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return user ? <JournalApp /> : <AuthForm />;
};

export default App;
