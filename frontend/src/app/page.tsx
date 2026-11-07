import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <div className="landing-card">
        <div className="brand-mark">P</div>
        <p className="eyebrow">PAYMENT CALLBACK WORKBENCH</p>
        <h1>See every webhook.<br /><span>Fix integrations faster.</span></h1>
        <p className="landing-copy">
          Capture and inspect JazzCash, EasyPaisa, PayFast, and any HTTP callback in real time.
        </p>
        <Link className="primary-button" href={`/inspect/${crypto.randomUUID()}`}>
          Create a local endpoint <span aria-hidden="true">→</span>
        </Link>
        <p className="landing-note">Your endpoint ID is generated in this browser.</p>
      </div>
    </main>
  );
}
