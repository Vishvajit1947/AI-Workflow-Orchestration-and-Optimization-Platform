/**
 * Two-panel authentication layout: branding left, form right.
 */

import React, { ReactNode } from 'react';
import { Network } from 'lucide-react';

interface AuthLayoutProps {
  children: ReactNode;
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex">
      {/* Left Panel: Branding */}
      <div className="hidden lg:flex lg:w-[55%] bg-surface-900 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-500/20 to-primary-600/10" />
        
        <div className="relative z-10 flex flex-col justify-center px-12 xl:px-20 w-full">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-full bg-primary-500 flex items-center justify-center">
              <Network className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white">AI Orchestrator</h1>
          </div>

          {/* Tagline */}
          <h2 className="text-4xl font-bold text-white mb-4">
            Orchestrate AI. Simplify Work.
          </h2>

          {/* Description */}
          <p className="text-lg text-gray-300 mb-12 max-w-lg">
            Build, execute, and optimize intelligent workflows using multiple AI
            models through one unified workspace.
          </p>

          {/* DAG Illustration */}
          <svg
            className="w-full max-w-md"
            viewBox="0 0 400 200"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Connections */}
            <line x1="80" y1="100" x2="160" y2="60" stroke="#10b981" strokeWidth="2" opacity="0.6" />
            <line x1="80" y1="100" x2="160" y2="140" stroke="#10b981" strokeWidth="2" opacity="0.6" />
            <line x1="200" y1="60" x2="280" y2="100" stroke="#10b981" strokeWidth="2" opacity="0.6" />
            <line x1="200" y1="140" x2="280" y2="100" stroke="#10b981" strokeWidth="2" opacity="0.6" />
            <line x1="320" y1="100" x2="380" y2="100" stroke="#10b981" strokeWidth="2" opacity="0.6" />

            {/* Nodes */}
            <circle cx="80" cy="100" r="20" fill="#10b981" opacity="0.8" />
            <circle cx="180" cy="60" r="20" fill="#10b981" opacity="0.8" />
            <circle cx="180" cy="140" r="20" fill="#10b981" opacity="0.8" />
            <circle cx="300" cy="100" r="20" fill="#10b981" opacity="0.8" />
            <circle cx="380" cy="100" r="15" fill="#34d399" opacity="0.8" />

            {/* Labels */}
            <text x="80" y="105" textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
              Start
            </text>
            <text x="180" y="65" textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
              AI
            </text>
            <text x="180" y="145" textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
              AI
            </text>
            <text x="300" y="105" textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
              Merge
            </text>
          </svg>
        </div>
      </div>

      {/* Right Panel: Form Content */}
      <div className="w-full lg:w-[45%] flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          {children}
        </div>
      </div>
    </div>
  );
}
