import { useEffect, useRef } from "react";

// Illustrative frequency layers, never presented as a measurement of user audio.
export default function SignalScene({ theme }) {
  const hostRef = useRef(null);
  useEffect(() => {
    const host = hostRef.current;
    let cancelled = false;
    let dispose = () => {};
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        observer.disconnect();
        import("./signalRenderer.js")
          .then(({ createSignalRenderer }) => {
            if (!cancelled) dispose = createSignalRenderer(host, theme);
          })
          .catch(() => {
            /* The static spectrum remains visible. */
          });
      },
      { rootMargin: "100px" },
    );
    observer.observe(host);
    return () => {
      cancelled = true;
      observer.disconnect();
      dispose();
    };
  }, [theme]);

  return (
    <div
      className="signal-scene"
      ref={hostRef}
      role="img"
      aria-label="Illustrated three-dimensional frequency spectrum, from low frequencies to high frequencies"
    >
      <svg className="signal-fallback" viewBox="0 0 460 270" aria-hidden="true">
        {Array.from({ length: 15 }, (_, row) => (
          <polyline
            key={row}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            opacity={0.3 + row / 24}
            points={Array.from({ length: 100 }, (_, i) => {
              const x = i / 99;
              const h =
                Math.exp(-Math.pow((x - 0.34) * 6, 2)) * 65 +
                Math.exp(-Math.pow((x - 0.68) * 10, 2)) * 38;
              return `${20 + x * 350 + row * 4},${182 - row * 6 - h * (0.65 + 0.35 * Math.sin(x * 23 + row * 0.3))}`;
            }).join(" ")}
          />
        ))}
      </svg>
    </div>
  );
}
