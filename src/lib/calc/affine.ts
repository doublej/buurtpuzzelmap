// Solve a 2D affine transform that maps src points to dst points
// in the least-squares sense. Returns [a, b, c, d, tx, ty]
// such that dst.x = a*src.x + b*src.y + tx, dst.y = c*src.x + d*src.y + ty.
export function solveAffine2D(
  src: ReadonlyArray<readonly [number, number]>,
  dst: ReadonlyArray<readonly [number, number]>
): [number, number, number, number, number, number] {
  const n = src.length;
  if (n !== dst.length || n < 3) throw new Error('need >=3 matching pairs');

  // Build (2n x 6) matrix and (2n) vector; solve via normal equations.
  const M: number[][] = [];
  const v: number[] = [];
  for (let i = 0; i < n; i++) {
    const [sx, sy] = src[i];
    const [dx, dy] = dst[i];
    M.push([sx, sy, 0, 0, 1, 0]); v.push(dx);
    M.push([0, 0, sx, sy, 0, 1]); v.push(dy);
  }
  // Solve via (M^T M) x = M^T v with Gaussian elimination on 6x7 augmented.
  const k = 6;
  const A = Array.from({ length: k }, () => new Array<number>(k).fill(0));
  const b = new Array<number>(k).fill(0);
  for (let i = 0; i < M.length; i++) {
    for (let r = 0; r < k; r++) {
      b[r] += M[i][r] * v[i];
      for (let c = 0; c < k; c++) A[r][c] += M[i][r] * M[i][c];
    }
  }
  // Gaussian elimination on [A | b]
  for (let i = 0; i < k; i++) {
    let pivot = i;
    for (let r = i + 1; r < k; r++) if (Math.abs(A[r][i]) > Math.abs(A[pivot][i])) pivot = r;
    if (pivot !== i) { [A[i], A[pivot]] = [A[pivot], A[i]]; [b[i], b[pivot]] = [b[pivot], b[i]]; }
    const p = A[i][i];
    if (Math.abs(p) < 1e-12) throw new Error('singular system');
    for (let c = i; c < k; c++) A[i][c] /= p;
    b[i] /= p;
    for (let r = 0; r < k; r++) {
      if (r === i) continue;
      const f = A[r][i];
      if (f === 0) continue;
      for (let c = i; c < k; c++) A[r][c] -= f * A[i][c];
      b[r] -= f * b[i];
    }
  }
  return [b[0], b[1], b[2], b[3], b[4], b[5]];
}

export function applyAffine(
  [a, b, c, d, tx, ty]: readonly [number, number, number, number, number, number],
  x: number,
  y: number
): [number, number] {
  return [a * x + b * y + tx, c * x + d * y + ty];
}
