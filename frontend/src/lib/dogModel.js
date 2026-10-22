import * as THREE from 'three';

const DEFAULT_PROFILE = {
  id: 'labrador', coat: 0xc79c60, darkCoat: 0x65422e, lightCoat: 0xf3e8d4,
  bodyLength: 1, bodyHeight: 1, legLength: 1, muzzleLength: 1,
  earLength: 1, headScale: 1, pattern: 'solid',
};

const boundedSize = value => Number.isFinite(value) ? THREE.MathUtils.clamp(value, .65, 1.35) : 1;
const smooth = (a, b, value) => THREE.MathUtils.smoothstep(value, a, b);

/**
 * A procedural visual stand-in until a fitted Blender/GLB asset is supplied.
 * Size fields are relative multipliers, not physical measurements. The dog faces
 * negative X; its standing paws sit on Y=0. No renderer, DOM, or textures needed.
 */
export function createDogModel(profile = {}) {
  const options = { ...DEFAULT_PROFILE, ...(profile || {}) };
  for (const key of ['bodyLength', 'bodyHeight', 'legLength', 'muzzleLength', 'earLength', 'headScale']) {
    options[key] = boundedSize(options[key]);
  }
  if (!['solid', 'tricolor', 'spots'].includes(options.pattern)) options.pattern = 'solid';
  const coat = new THREE.Color(options.coat ?? DEFAULT_PROFILE.coat);
  const dark = new THREE.Color(options.darkCoat ?? DEFAULT_PROFILE.darkCoat);
  const light = new THREE.Color(options.lightCoat ?? DEFAULT_PROFILE.lightCoat);
  const black = new THREE.Color(0x202322);
  const brown = new THREE.Color(0x5b341d);
  const group = new THREE.Group(); group.name = 'procedural-dog';
  group.userData.profile = { ...options };
  group.userData.visualApproximation = true;
  const body = new THREE.Group(); body.name = 'dog-body'; group.add(body);
  const geometries = new Set(), materials = new Set();
  const materialCache = new Map();
  const ownGeometry = geometry => { geometries.add(geometry); return geometry; };
  const material = (color, roughness = .86, vertexColors = false) => {
    const key = `${color.getHexString()}-${roughness}-${vertexColors}`;
    if (!materialCache.has(key)) {
      const item = new THREE.MeshStandardMaterial({ color, roughness, vertexColors });
      materials.add(item); materialCache.set(key, item);
    }
    return materialCache.get(key);
  };
  const L = options.bodyLength, H = options.bodyHeight, S = options.headScale;
  const upperLength = .68 * options.legLength, lowerLength = .65 * options.legLength;
  const hipY = upperLength + lowerLength + .13;
  const torsoY = hipY + .22 * H;

  // Small irregular patches are defined on the coat surface, not on a screen
  // texture. Their deterministic positions make repeated alignment consistent.
  const spots = [
    [-1.03, .22, .46, .14], [-.72, .39, .42, .16], [-.37, .02, .56, .12],
    [-.11, .43, .35, .15], [.25, .10, .54, .17], [.59, .38, .43, .13],
    [.94, -.05, .49, .15], [1.09, .32, .29, .12], [-.68, -.19, .48, .11],
    [.12, -.30, .40, .11], [.72, -.33, .35, .14], [-.28, .54, .06, .14],
    [.57, .54, -.03, .16], [-.93, .11, -.48, .15], [-.56, .36, -.45, .12],
    [-.21, -.02, -.56, .17], [.18, .38, -.43, .13], [.51, -.13, -.53, .12],
    [.86, .21, -.45, .16], [1.07, -.17, -.34, .12], [-.55, -.31, -.39, .11],
  ];
  function bodyColor(x, y, z) {
    if (options.pattern === 'solid') {
      const underside = 1 - smooth(torsoY - .38 * H, torsoY + .2 * H, y);
      return coat.clone().lerp(light, underside * .14);
    }
    if (options.pattern === 'tricolor') {
      const saddle = smooth(-.92 * L, -.52 * L, x) * (1 - smooth(1.12 * L, 1.43 * L, x))
        * smooth(torsoY - .32 * H, torsoY + .05 * H, y);
      const tan = smooth(torsoY - .32 * H, torsoY + .08 * H, y);
      return light.clone().lerp(coat, tan).lerp(dark, saddle);
    }
    let ink = 0;
    for (const [sx, sy, sz, radius] of spots) {
      const dx = (x / L - sx), dy = (y - torsoY) / H - sy, dz = z - sz;
      const distance = Math.sqrt(dx * dx + dy * dy * 1.15 + dz * dz);
      ink = Math.max(ink, 1 - smooth(radius * .76, radius * 1.1, distance));
    }
    return coat.clone().lerp(dark, ink);
  }
  function mesh(name, geometry, color, parent = body, paint = null, roughness = .86) {
    ownGeometry(geometry);
    if (paint) {
      const position = geometry.getAttribute('position'), colors = [];
      for (let i = 0; i < position.count; i++) {
        const result = paint(position.getX(i), position.getY(i), position.getZ(i));
        colors.push(result.r, result.g, result.b);
      }
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    }
    const item = new THREE.Mesh(geometry, material(paint ? new THREE.Color(0xffffff) : color, roughness, Boolean(paint)));
    item.name = name; item.castShadow = true; item.receiveShadow = true; parent.add(item);
    return item;
  }
  function ellipsoid(name, position, scale, color, parent = body, paint = null, segments = 28) {
    const geometry = new THREE.SphereGeometry(1, segments, Math.max(12, Math.floor(segments * .65)));
    geometry.scale(...scale); geometry.translate(...position);
    return mesh(name, geometry, color, parent, paint);
  }
  function tube(name, points, radii, color, parent = body, paint = null, segments = 32, sides = 12) {
    const curve = new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point)));
    const frames = curve.computeFrenetFrames(segments, false);
    const vertices = [], indices = [];
    for (let i = 0; i <= segments; i++) {
      const t = i / segments, center = curve.getPointAt(t), at = t * (radii.length - 1);
      const radius = THREE.MathUtils.lerp(radii[Math.floor(at)], radii[Math.min(Math.ceil(at), radii.length - 1)], at % 1);
      for (let j = 0; j <= sides; j++) {
        const angle = j / sides * Math.PI * 2;
        const point = center.clone().addScaledVector(frames.normals[i], Math.cos(angle) * radius)
          .addScaledVector(frames.binormals[i], Math.sin(angle) * radius);
        vertices.push(point.x, point.y, point.z);
        if (i < segments && j < sides) {
          const a = i * (sides + 1) + j, b = a + sides + 1;
          indices.push(a, a + 1, b, b, a + 1, b + 1);
        }
      }
    }
    // Rounded paths taper almost to a point; close their tiny end rings too.
    for (const [ring, reverse] of [[0, true], [segments, false]]) {
      for (let j = 1; j < sides - 1; j++) {
        const a = ring * (sides + 1);
        indices.push(a, a + (reverse ? j + 1 : j), a + (reverse ? j : j + 1));
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setIndex(indices); geometry.computeVertexNormals();
    return mesh(name, geometry, color, parent, paint);
  }

  // Lofted oval rings give the chest, abdominal tuck, and rump one continuous
  // silhouette instead of the old row of visibly overlapping spheres.
  const sections = [
    [-1.35, -.02, .03, .04], [-1.25, .03, .37, .36], [-1.05, .02, .56, .49],
    [-.76, .01, .62, .55], [-.39, .01, .58, .54], [0, .04, .49, .46],
    [.37, .06, .43, .40], [.76, .03, .51, .46], [1.07, -.02, .48, .42],
    [1.30, -.06, .30, .28], [1.40, -.07, .025, .035],
  ];
  const torsoCurve = new THREE.CatmullRomCurve3(sections.map(([x, y, ry, rz]) => new THREE.Vector3(x, y, 0)));
  const sectionCurve = new THREE.CatmullRomCurve3(sections.map(([x, y, ry, rz]) => new THREE.Vector3(x, ry, rz)));
  const torsoPositions = [], torsoIndices = [], rings = 64, around = 48;
  for (let i = 0; i <= rings; i++) {
    const center = torsoCurve.getPoint(i / rings), section = sectionCurve.getPoint(i / rings);
    for (let j = 0; j <= around; j++) {
      const angle = j / around * Math.PI * 2;
      torsoPositions.push(center.x * L, torsoY + center.y * H + Math.cos(angle) * section.y * H, Math.sin(angle) * section.z);
      if (i < rings && j < around) {
        const a = i * (around + 1) + j, b = a + around + 1;
        torsoIndices.push(a, a + 1, b, b, a + 1, b + 1);
      }
    }
  }
  const torsoGeometry = new THREE.BufferGeometry();
  torsoGeometry.setAttribute('position', new THREE.Float32BufferAttribute(torsoPositions, 3));
  torsoGeometry.setIndex(torsoIndices); torsoGeometry.computeVertexNormals();
  mesh('torso', torsoGeometry, coat, body, bodyColor);

  ellipsoid('chest-keel', [-.92 * L, hipY + .10 * H, 0], [.35 * L, .43 * H, .37],
    options.pattern === 'tricolor' ? light : coat);
  const neck = ellipsoid('neck', [-1.07 * L, hipY + .62 * H, 0], [.43 * S, .64 * H, .36 * S], coat);
  // Rotate around the neck center without moving its attachment point.
  neck.geometry.translate(1.07 * L, -hipY - .62 * H, 0);
  neck.geometry.rotateZ(-.34);
  neck.geometry.translate(-1.07 * L, hipY + .62 * H, 0);
  if (options.pattern === 'tricolor') {
    ellipsoid('white-bib', [-1.30 * L, hipY + .40 * H, 0], [.24 * S, .48 * H, .29 * S], light);
  }
  const head = new THREE.Group(); head.name = 'head-assembly';
  head.position.set(-1.12 * L, hipY + .65 * H, 0); body.add(head);
  const headColor = options.pattern === 'spots' ? coat : coat.clone().lerp(light, .08);
  const headPaint = options.pattern === 'spots' ? (x, y, z) => {
    const patch = Math.exp(-((x + .31 * S) ** 2 / .019 + (y - .40 * S) ** 2 / .032 + (Math.abs(z) - .27 * S) ** 2 / .015));
    return coat.clone().lerp(dark, smooth(.28, .65, patch));
  } : null;
  ellipsoid('skull', [-.40 * S, .26 * S, 0], [.49 * S, .39 * S, .345 * S], headColor, head, headPaint, 36);
  ellipsoid('brow', [-.64 * S, .33 * S, 0], [.30 * S, .19 * S, .315 * S], headColor, head);
  const muzzleX = -.76 * S - .13 * options.muzzleLength;
  const muzzleColor = options.pattern === 'solid' ? coat.clone().lerp(light, .32) : light;
  ellipsoid('muzzle', [muzzleX, .02 * S, 0], [.38 * options.muzzleLength * S, .225 * S, .27 * S], muzzleColor, head, null, 32);
  ellipsoid('lower-jaw', [muzzleX + .05 * S, -.12 * S, 0], [.32 * options.muzzleLength * S, .105 * S, .225 * S], muzzleColor, head);
  const noseX = muzzleX - .34 * options.muzzleLength * S;
  ellipsoid('nose', [noseX, .05 * S, 0], [.11 * S, .105 * S, .18 * S], black, head, null, 24);
  for (const side of [-1, 1]) {
    ellipsoid(`nostril-${side}`, [noseX - .082 * S, .064 * S, side * .078 * S], [.021 * S, .022 * S, .035 * S], black.clone().multiplyScalar(.45), head, null, 12);
    ellipsoid(`eye-socket-${side}`, [-.66 * S, .34 * S, side * .288 * S], [.108 * S, .087 * S, .050 * S], coat.clone().multiplyScalar(.63), head);
    ellipsoid(`eye-${side}`, [-.688 * S, .342 * S, side * .322 * S], [.062 * S, .060 * S, .026 * S], brown, head, null, 20);
    ellipsoid(`pupil-${side}`, [-.703 * S, .343 * S, side * .341 * S], [.035 * S, .038 * S, .011 * S], black, head, null, 16);
    ellipsoid(`eye-glint-${side}`, [-.716 * S, .361 * S, side * .350 * S], [.010 * S, .011 * S, .005 * S], new THREE.Color(0xffffff), head, null, 12);
    tube(`lip-${side}`, [[noseX + .08 * S, -.07 * S, side * .14 * S], [muzzleX, -.125 * S, side * .223 * S], [-.57 * S, -.064 * S, side * .228 * S]], [.009 * S, .011 * S, .008 * S], dark.clone().multiplyScalar(.65), head, null, 18, 6);
    const earLength = .65 * options.earLength * S;
    const earPositions = [], earIndices = [], earRings = 18, earAround = 20;
    for (let i = 0; i <= earRings; i++) {
      const t = i / earRings, width = (.16 + Math.sin(t * Math.PI) * .07) * Math.sqrt(1 - t * .97) * S;
      const center = new THREE.Vector3(-.16 * S + .12 * S * Math.sin(t * 1.7), .55 * S - t * earLength,
        side * (.28 * S + .15 * S * Math.sin(t * Math.PI * .82)));
      for (let j = 0; j <= earAround; j++) {
        const theta = j / earAround * Math.PI * 2;
        earPositions.push(center.x + Math.cos(theta) * width, center.y,
          center.z + Math.sin(theta) * (.055 * S * (1 - t) + .012 * S));
        if (i < earRings && j < earAround) {
          const a = i * (earAround + 1) + j, b = a + earAround + 1;
          earIndices.push(a, a + 1, b, b, a + 1, b + 1);
        }
      }
    }
    const earGeometry = new THREE.BufferGeometry();
    earGeometry.setAttribute('position', new THREE.Float32BufferAttribute(earPositions, 3));
    earGeometry.setIndex(earIndices); earGeometry.computeVertexNormals();
    mesh(`ear-${side}`, earGeometry, options.pattern === 'spots' ? dark : coat.clone().lerp(dark, .35), head);
  }
  if (options.pattern === 'tricolor') {
    ellipsoid('forehead-blaze', [-.78 * S, .37 * S, 0], [.13 * S, .27 * S, .12 * S], light, head);
  }

  const legs = [];
  for (const front of [true, false]) for (const side of [-1, 1]) {
    const name = `${front ? 'front' : 'hind'}-${side === 1 ? 'near' : 'far'}`;
    const upper = new THREE.Group(); upper.name = `${name}-upper-joint`;
    const standingUpper = front ? .025 : -.36, standingLower = front ? -.025 : .64;
    upper.position.set((front ? -.89 : .97) * L,
      front ? hipY : Math.cos(standingUpper) * upperLength + Math.cos(standingUpper + standingLower) * lowerLength + .13,
      side * (front ? .36 : .33)); body.add(upper);
    const limbColor = coat;
    ellipsoid(`${name}-shoulder`, [0, -.21 * options.legLength, 0],
      [front ? .20 : .265, upperLength * .56, front ? .19 : .235], limbColor, upper);
    const upperBone = new THREE.CylinderGeometry(front ? .14 : .18, .105, upperLength, 18, 1);
    upperBone.translate(0, -upperLength / 2, 0);
    mesh(`${name}-upper-leg`, upperBone, limbColor, upper);
    const lower = new THREE.Group(); lower.name = `${name}-lower-joint`;
    lower.position.y = -upperLength; upper.add(lower);
    ellipsoid(`${name}-joint`, [0, -.015, 0], [.112, .14, .115], limbColor, lower);
    const lowerBone = new THREE.CylinderGeometry(.105, .068, lowerLength, 16, 1);
    lowerBone.translate(0, -lowerLength / 2, 0);
    mesh(`${name}-lower-leg`, lowerBone, options.pattern === 'tricolor' ? light : coat, lower);
    const paw = new THREE.Group(); paw.name = `${name}-paw`; paw.position.y = -lowerLength; lower.add(paw);
    const pawColor = options.pattern === 'solid' ? coat.clone().lerp(light, .17) : light;
    ellipsoid(`${name}-foot`, [-.075, -.008, .008 * side], [.235, .103, .145], pawColor, paw, null, 20);
    for (let toe = -1; toe <= 1; toe++) {
      ellipsoid(`${name}-toe-${toe}`, [-.23, -.018, toe * .080], [.093, .077, .053], pawColor, paw, null, 12);
      ellipsoid(`${name}-claw-${toe}`, [-.31, -.012, toe * .080], [.027, .024, .020], dark.clone().lerp(light, .22), paw, null, 10);
    }
    if (options.pattern === 'spots') {
      ellipsoid(`${name}-leg-spot`, [-.07, -.23 * options.legLength, side * .177], [.075, .095, .014], dark, upper, null, 16);
      ellipsoid(`${name}-ankle-spot`, [-.018, -.40 * options.legLength, side * .072], [.050, .065, .010], dark, lower, null, 12);
    }
    legs.push({ upper, lower, paw, front, standingUpper, standingLower });
  }
  const tail = new THREE.Group(); tail.name = 'tail-assembly';
  tail.position.set(1.23 * L, torsoY + .08 * H, 0); body.add(tail);
  const tailColor = options.pattern === 'tricolor' ? dark : coat;
  tube('tail', [[0, 0, 0], [.30, .06, .01], [.66, .01, .015], [.98, -.15, .04], [1.21, -.26, .07]],
    [.15, .125, .086, .050, .008], tailColor, tail, options.pattern === 'tricolor' ? (x) => dark.clone().lerp(light, smooth(.80, .98, x)) : null, 36, 14);

  let disposed = false;
  function setPose(blend = 0) {
    if (disposed) return;
    const value = Number.isFinite(blend) ? THREE.MathUtils.clamp(blend, 0, 1) : 0;
    let lowestSupport = torsoY - .62 * H;
    for (const leg of legs) {
      const upperAngle = THREE.MathUtils.lerp(leg.standingUpper, leg.front ? -1.25 : -1.35, value);
      const lowerAngle = THREE.MathUtils.lerp(leg.standingLower, leg.front ? 2.65 : 2.80, value);
      leg.upper.rotation.z = upperAngle; leg.lower.rotation.z = lowerAngle;
      leg.paw.rotation.z = -upperAngle - lowerAngle;
      const pawY = leg.upper.position.y - Math.cos(upperAngle) * upperLength - Math.cos(upperAngle + lowerAngle) * lowerLength;
      const thighRadiusX = leg.front ? .20 : .265;
      const thighBottom = leg.upper.position.y - .21 * options.legLength * Math.cos(upperAngle)
        - Math.hypot(thighRadiusX * Math.sin(upperAngle), upperLength * .56 * Math.cos(upperAngle));
      lowestSupport = Math.min(lowestSupport, pawY - .111, thighBottom);
    }
    // Translate using the actual articulated endpoints so the paws keep their
    // floor contact as the four legs fold into a supported resting position.
    body.position.y = -lowestSupport;
    head.rotation.z = value * .07;
    tail.rotation.z = (options.pattern === 'tricolor' ? .54 : .05) - value * .20;
    group.userData.poseBlend = value;
    group.updateMatrixWorld(true);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    geometries.forEach(geometry => geometry.dispose());
    materials.forEach(item => item.dispose());
    group.removeFromParent();
  }
  setPose(0);
  return { group, setPose, dispose };
}
