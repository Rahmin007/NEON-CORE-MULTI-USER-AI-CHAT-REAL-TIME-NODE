import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <main className="grid min-h-[100dvh] place-items-center p-6 text-center">
      <div>
        <p className="font-display text-7xl font-extrabold text-cyan">404</p>
        <p className="mt-3 text-muted">This node doesn&apos;t exist.</p>
        <Link to="/" className="mt-6 inline-block font-display text-xs font-bold tracking-widest text-pink underline">
          BACK TO THE LOBBY
        </Link>
      </div>
    </main>
  );
}
