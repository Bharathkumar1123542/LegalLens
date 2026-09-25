'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getAccessToken, clearAuthTokens, refreshAccessToken, setAuthTokens } from '@/lib/api-client';
import { isTokenExpired, getTokenExpiryTime, getUserFromToken } from '@/lib/jwt-helper';
import type { User } from '@/types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Setup token refresh timer
  const setupRefreshTimer = useCallback((token: string) => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    const expiryTime = getTokenExpiryTime(token);
    if (!expiryTime) return;

    // Refresh 1 minute before expiry
    const refreshTime = Math.max(expiryTime - 60000, 0);

    console.log(`Token refresh scheduled in ${Math.floor(refreshTime / 1000)}s`);

    refreshTimerRef.current = setTimeout(async () => {
      console.log('Auto-refreshing token...');
      try {
        const tokens = await refreshAccessToken();
        setAuthTokens(tokens);
        
        // Extract user info from new token
        const userInfo = getUserFromToken(tokens.access_token);
        if (userInfo) {
          setUser({
            id: userInfo.id,
            email: userInfo.email,
            full_name: userInfo.name,
            role: 'user',
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          });
        }

        // Setup next refresh
        setupRefreshTimer(tokens.access_token);
      } catch (error) {
        console.error('Token refresh failed:', error);
        logout();
      }
    }, refreshTime);
  }, []);

  // Initialize auth state from localStorage
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      // Check if token is expired
      if (isTokenExpired(token)) {
        console.log('Token expired on load, attempting refresh...');
        refreshAccessToken()
          .then((tokens) => {
            setAuthTokens(tokens);
            const userInfo = getUserFromToken(tokens.access_token);
            if (userInfo) {
              setUser({
                id: userInfo.id,
                email: userInfo.email,
                full_name: userInfo.name,
                role: 'user',
                is_active: true,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              });
            }
            setupRefreshTimer(tokens.access_token);
          })
          .catch(() => {
            clearAuthTokens();
          })
          .finally(() => {
            setIsLoading(false);
          });
      } else {
        // Token is valid, extract user info
        const userInfo = getUserFromToken(token);
        if (userInfo) {
          setUser({
            id: userInfo.id,
            email: userInfo.email,
            full_name: userInfo.name,
            role: 'user',
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          });
        }
        setupRefreshTimer(token);
        setIsLoading(false);
      }
    } else {
      setIsLoading(false);
    }

    // Cleanup timer on unmount
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [setupRefreshTimer]);

  const login = useCallback((accessToken: string, refreshToken: string) => {
    setAuthTokens({ access_token: accessToken, refresh_token: refreshToken, token_type: 'bearer' });
    
    const userInfo = getUserFromToken(accessToken);
    if (userInfo) {
      setUser({
        id: userInfo.id,
        email: userInfo.email,
        full_name: userInfo.name,
        role: 'user',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    }

    setupRefreshTimer(accessToken);
  }, [setupRefreshTimer]);

  const logout = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    clearAuthTokens();
    setUser(null);
    router.push('/auth/login');
  }, [router]);

  const refreshAuth = useCallback(async () => {
    try {
      const tokens = await refreshAccessToken();
      setAuthTokens(tokens);
      setupRefreshTimer(tokens.access_token);
    } catch (error) {
      logout();
    }
  }, [setupRefreshTimer, logout]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
