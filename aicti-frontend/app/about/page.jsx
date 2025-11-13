import Link from 'next/link'

export const metadata = {
  title: 'About • AI-CTI',
  description: 'Learn how the AI-CTI newsroom gathers, enriches, and shares cyber threat intelligence.',
}

const contributors = [
  {
    title: 'Founder & Builder',
    name: 'Nishant',
    description:
      'Product engineer and security enthusiast focused on translating raw threat data into newsroom-grade intelligence.',
    linkedin: 'https://www.linkedin.com/in/normienishant/',
    github: 'https://github.com/normienishant',
  },
  {
    title: 'AI Research & Automation',
    name: 'AI Copilot',
    description:
      'Supports ingestion, enrichment, and clustering pipelines using Python, FastAPI, and Supabase orchestration.',
  },
]

const pillars = [
  {
    headline: 'Live Threat Coverage',
    body: 'RSS and JSON feeds from trusted security desks (ThreatPost, DarkReading, BleepingComputer, CSO, SecurityWeek, and more) are fetched every 30 minutes, enriched, and served to the dashboard.',
  },
  {
    headline: 'OG Thumbnails & IOC Extraction',
    body: 'Every article is scanned for OpenGraph/Twitter images and enriched with IP, domain, and CVE indicators using a lightweight IOC extractor.',
  },
  {
    headline: 'Zero Local Storage',
    body: 'Articles, imagery, and indicators are pushed to Supabase Storage + Postgres so deployments stay stateless and the local filesystem remains clean.',
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
            A newsroom-grade desk for cyber threat intelligence teams
          </h1>
          <p className="small-muted" style={{ maxWidth: 680 }}>
            AI-CTI blends automated data collection with a polished analyst workflow so you can monitor ransomware
            crews, zero-day exploits, and breach disclosures the moment they surface.
          </p>
        </header>

        <div className="sidebar-card" style={{ display: 'grid', gap: 18 }}>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>How the pipeline works</h2>
          <ol style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 12, color: '#475569' }}>
            <li>
              <strong>Ingest & Normalise.</strong> A FastAPI service polls vetted security feeds, converts raw RSS into
              structured JSON, and cleans the metadata for downstream processing.
            </li>
            <li>
              <strong>Enrich.</strong> For every story we resolve OG/Twitter imagery, extract IOCs (IP, domain, CVE),
              and stamp the originating source so analysts can triage quickly.
            </li>
            <li>
              <strong>Store safely.</strong> Articles, thumbnails, and indicators are stored in Supabase tables &
              buckets—keeping deployments stateless and the project ready for serverless scaling.
            </li>
            <li>
              <strong>Publish.</strong> The Next.js dashboard reads from Supabase on demand, batches updates every five
              minutes, and surfaces trending topics, desk status, and indicators without a manual refresh.
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
          <h2 style={{ fontSize: '1.1rem', margin: 0 }}>Who&apos;s behind the desk?</h2>
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
            The roadmap includes analyst annotations, IOC export APIs, dark-mode, and richer clustering visuals. Open an
            issue or send a pull request if you want to collaborate.
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
              href="https://www.linkedin.com/in/normienishant/"
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
