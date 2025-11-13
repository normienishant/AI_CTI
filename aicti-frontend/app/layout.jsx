import './globals.css';
import ThemeProvider from '../components/theme/ThemeProvider';
import ThemeToggle from '../components/theme/ThemeToggle';
import SavedBriefingsProvider from '../components/saved/SavedBriefingsProvider';

export const metadata = {
  title: 'AI-CTI — Cyber Threat News',
  description: 'Live cyber threat news, feeds & IOC analysis',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <SavedBriefingsProvider>
            <header className="site-header">
              <div className="container header-inner">
                <div className="brand">
                  <div className="logo-mark" aria-hidden="true">
                    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <rect x="1" y="1" width="34" height="34" rx="10" fill="url(#grad)" />
                      <path
                        d="M18 9L26 24H10L18 9Z"
                        fill="white"
                        opacity="0.9"
                      />
                      <defs>
                        <linearGradient id="grad" x1="4" y1="4" x2="30" y2="32" gradientUnits="userSpaceOnUse">
                          <stop stopColor="#2563eb" />
                          <stop offset="1" stopColor="#1e40af" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                  <div>
                    <div className="site-title">AI-CTI</div>
                    <div className="site-sub">Cyber threat news & IOC analysis</div>
                  </div>
                </div>

                <nav className="main-nav">
                  <a href="/dashboard">Home</a>
                  <a href="/about">About</a>
                  <a href="/intel">Intel dashboard</a>
                  <a href="https://github.com/normienishant/AI_CTI" target="_blank" rel="noreferrer">GitHub</a>
                  <ThemeToggle />
                </nav>
              </div>
            </header>

            <main>{children}</main>

            <footer className="site-footer">
              <div className="container">
                © {new Date().getFullYear()} AI-CTI — curated cyber threat feeds • Built by Nishant
              </div>
            </footer>
          </SavedBriefingsProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}

