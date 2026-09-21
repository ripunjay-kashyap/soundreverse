import * as THREE from "three";

export function createSignalRenderer(host, theme) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "low-power",
    });
  } catch {
    return () => {};
  }
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const mobile = window.matchMedia("(max-width: 700px)");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0, 3.8, 7.5);
  camera.lookAt(0, 0.45, 0);
  const group = new THREE.Group();
  group.rotation.y = -0.28;
  scene.add(group);
  const geometries = [],
    materials = [];
  const count = mobile.matches ? 16 : 28;
  for (let row = 0; row < count; row++) {
    const vertices = [];
    for (let i = 0; i <= 100; i++) {
      const x = i / 100;
      const peak =
        Math.exp(-Math.pow((x - 0.33) * 6, 2)) * 1.6 +
        Math.exp(-Math.pow((x - 0.7) * 10, 2)) * 0.85;
      const height = peak * (0.66 + 0.34 * Math.sin(x * 24 + row * 0.2));
      vertices.push((x - 0.5) * 5.4, height, (row / (count - 1) - 0.5) * 2.7);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(vertices, 3),
    );
    const color = new THREE.Color(
      theme === "dark" ? "#ffb188" : "#a24325",
    ).lerp(
      new THREE.Color(theme === "dark" ? "#999ae5" : "#6b66a0"),
      row / count,
    );
    const material = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.5 + (row / count) * 0.5,
    });
    geometries.push(geometry);
    materials.push(material);
    group.add(new THREE.Line(geometry, material));
  }
  renderer.setPixelRatio(
    Math.min(window.devicePixelRatio || 1, mobile.matches ? 1 : 1.5),
  );
  host.appendChild(renderer.domElement);
  renderer.domElement.setAttribute("aria-hidden", "true");
  let visible = true,
    target = -0.28,
    lost = false;
  const render = () => {
    if (!lost) renderer.render(scene, camera);
  };
  const resize = () => {
    const { width, height } = host.getBoundingClientRect();
    renderer.setSize(width, height);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
    render();
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);
  const loop = () => {
    renderer.setAnimationLoop(null);
    if (
      !reduced.matches &&
      !mobile.matches &&
      visible &&
      !document.hidden &&
      !lost
    ) {
      renderer.setAnimationLoop((time) => {
        group.rotation.y += (target - group.rotation.y) * 0.035;
        group.position.y = Math.sin(time * 0.00045) * 0.035;
        render();
      });
    } else render();
  };
  const visibility = new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    loop();
  });
  visibility.observe(host);
  const move = (e) => {
    if (!reduced.matches && !mobile.matches)
      target = -0.28 + (e.offsetX / host.clientWidth - 0.5) * 0.25;
  };
  const leave = () => {
    target = -0.28;
  };
  const onLost = (e) => {
    e.preventDefault();
    lost = true;
    renderer.setAnimationLoop(null);
    host.classList.remove("has-webgl");
  };
  const onRestored = () => {
    lost = false;
    resize();
    host.classList.add("has-webgl");
    loop();
  };
  host.addEventListener("pointermove", move);
  host.addEventListener("pointerleave", leave);
  renderer.domElement.addEventListener("webglcontextlost", onLost);
  renderer.domElement.addEventListener("webglcontextrestored", onRestored);
  document.addEventListener("visibilitychange", loop);
  reduced.addEventListener("change", loop);
  mobile.addEventListener("change", loop);
  resize();
  host.classList.add("has-webgl");
  loop();
  return () => {
    renderer.setAnimationLoop(null);
    visibility.disconnect();
    resizeObserver.disconnect();
    host.removeEventListener("pointermove", move);
    host.removeEventListener("pointerleave", leave);
    document.removeEventListener("visibilitychange", loop);
    reduced.removeEventListener("change", loop);
    mobile.removeEventListener("change", loop);
    renderer.domElement.removeEventListener("webglcontextlost", onLost);
    renderer.domElement.removeEventListener("webglcontextrestored", onRestored);
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    renderer.dispose();
    renderer.domElement.remove();
    host.classList.remove("has-webgl");
  };
}
