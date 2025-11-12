import './globals.css';

export const metadata = {
  title: 'AI-CTI — Cyber Threat News',
  description: 'Live cyber threat news, feeds & IOC analysis',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="container header-inner">
            <div className="brand">
              <div className="logo-pill">AI</div>
              <div>
                <div className="site-title">AI-CTI</div>
                <div className="site-sub">Cyber threat news & IOC analysis</div>
              </div>
            </div>

            <nav className="main-nav">
              <a href="/dashboard">Home</a>
              <a href="/about">About</a>
              <a href="https://github.com/normienishant" target="_blank" rel="noreferrer">GitHub</a>
            </nav>
          </div>
        </header>

        <main>{children}</main>

        <footer className="site-footer">
          <div className="container">
            © {new Date().getFullYear()} AI-CTI — curated cyber threat feeds • Built by Nishant
          </div>
        </footer>
      </body>
    </html>
  )
}

