import Link from 'next/link'

export const metadata = {
  title: 'About • AI-CTI',
  description: 'See how AI-CTI turns raw threat feeds into real-time, newsroom-style cyber intelligence.',
}

const contributors = [
  {
    title: 'Founder & Builder',
    name: 'Nishant',
    description:
      'Artificial Intelligence and Machine Learning Enthusiast.',
    linkedin: 'https://www.linkedin.com/in/designsbynishant/',
    github: 'https://github.com/normienishant',
  },
]

const pillars = [
  {
    headline: 'Live Threat Coverage',
    body: 'Curated RSS and JSON feeds (ThreatPost, DarkReading, BleepingComputer, CSO, SecurityWeek, and more) are pulled regularly, normalized, and funneled into the pipeline for instant processing.',
  },
  {
    headline: 'OG Thumbnails & IOC Extraction',
    body: 'Articles are scanned for OpenGraph/Twitter images and automatically scraped for indicators — IPs, domains, CVEs and other IOCs — so analysts see the important signals first.',
  },
  {
    headline: 'Zero Local Storage',
    body: 'All content and artifacts live in Supabase Storage + Postgres. Deployments stay stateless, portable, and CI/CD-friendly — no local baggage.',
  },
]

export default function AboutPage() {
  return (
    <section className="container" style={{ padding: '56px 24px', maxWidth: 960 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
        <header style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.28em' }}>
            About AI-CTI
          </span>
          <h1 className="h1" style={{ fontSize: '2.25rem', lineHeight: 1.2 }}>
            Real-time cyber intel. Zero noise.
          </h1>
          <p className="small-muted" style={{ maxWidth: 680 }}>
            AI-CTI combines continuous feed ingestion, automated enrichment, and a lean analyst UI so teams can spot ransomware campaigns,
            zero-days, and breaches the moment they appear — without digging through noise.
          </p>
        </header>

        <div className="sidebar-card" style={{ display: 'grid', gap: 18 }}>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>How the pipeline works</h2>
          <ol style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 12, color: '#475569' }}>
            <li>
              <strong>Ingest & Normalise.</strong> A FastAPI worker pulls trusted security feeds, turns raw RSS/JSON into structured objects, and normalizes metadata for fast downstream use.
            </li>
            <li>
              <strong>Enrich.</strong> Stories are enriched automatically — OG/Twitter thumbnails are resolved, indicators are extracted, and sources are tagged so analysts can prioritize quickly.
            </li>
            <li>
              <strong>Store safely.</strong> Articles, thumbnails, and IOCs are stored in Supabase Postgres + Storage, keeping deployments stateless and production-ready.
            </li>
            <li>
              <strong>Publish.</strong> The Next.js dashboard reads from Supabase on demand, batches updates, and surfaces trending topics and indicators without manual refreshes.
            </li>
          </ol>
        </div>

        <div style={{ display: 'grid', gap: 18 }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0 }}>What makes AI-CTI different</h2>
          <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            {pillars.map((pillar) => (
              <div key={pillar.headline} className="sidebar-card" style={{ height: '100%' }}>
                <h3 style={{ marginTop: 0, fontSize: '1rem' }}>{pillar.headline}</h3>
                <p className="small-muted" style={{ marginBottom: 0 }}>{pillar.body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0 }}>Connect with the creator</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {contributors.map((person) => (
              <div key={person.name} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748b' }}>
                  {person.title}
                </span>
                <span style={{ fontSize: '1rem', fontWeight: 600 }}>{person.name}</span>
                <p className="small-muted" style={{ marginBottom: 0 }}>{person.description}</p>
                {person.linkedin && (
                  <div style={{ display: 'flex', gap: 10 }}>
                    <a className="btn-ghost" href={person.linkedin} target="_blank" rel="noreferrer">
                      Connect on LinkedIn
                    </a>
                    {person.github && (
                      <a className="btn-ghost" href={person.github} target="_blank" rel="noreferrer">
                        GitHub Profile
                      </a>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0 }}>Want to extend AI-CTI?</h2>
          <p className="small-muted" style={{ marginBottom: 0 }}>
            Interested in features or integrations? Open an issue, send a PR, or reach out — contributions are appreciated.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <Link className="btn-primary" href="/dashboard">
              View live dashboard
            </Link>
            <a
              className="btn-ghost"
              href="https://github.com/normienishant/AI_CTI"
              target="_blank"
              rel="noreferrer"
            >
              Explore the repository
            </a>
            <a
              className="btn-ghost"
              href="https://www.linkedin.com/in/designsbynishant/"
              target="_blank"
              rel="noreferrer"
            >
              Message on LinkedIn
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
