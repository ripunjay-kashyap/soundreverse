const paths = {
  arrow: "M4 12h16m-6-6 6 6-6 6",
  wave: "M2 12h2m3-5v10m4-14v18m4-15v12m4-9v6m3-3h1",
  sliders: "M5 3v5m0 4v9M12 3v11m0 4v3M19 3v2m0 4v12M2 8h6m1 10h6m1-13h6",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4",
  upload: "M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4",
  headphones: "M4 14v-3a8 8 0 0 1 16 0v3M4 12H2v8h5v-8H4m16 0h2v8h-5v-8h3",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z",
  check: "m5 12 4 4L19 6",
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M18 6 6 18",
  alert: "m12 3 10 18H2L12 3Zm0 6v5m0 3v.1",
  music:
    "M9 18V5l11-2v13M9 5v5l11-2M9 18c0 4-7 4-7 1s7-4 7-1Zm11-2c0 4-7 4-7 1s7-4 7-1Z",
};
export default function Icon({ name, size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.wave} />
    </svg>
  );
}
