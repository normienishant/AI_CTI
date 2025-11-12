export default function Footer() {
  return (
    <footer className="site-footer container">
      <div>© {new Date().getFullYear()} AI-CTI — Live cyber threat news & indicators</div>
      <div style={{marginTop:8}}>Built with ❤️ · Data fetched from public threat feeds</div>
    </footer>
  );
}
