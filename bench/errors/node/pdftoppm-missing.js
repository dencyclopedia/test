// node-pdftoppm (README example) and node-poppler with no poppler-utils on PATH.
const which = process.argv[2];
const pdf = process.argv[3];
if (which === 'node-pdftoppm') {
  const pdf2ppm = require('node-pdftoppm');
  pdf2ppm(pdf, '/tmp', 'hello', (error, data) => {
    if (error) console.error('error', error); else console.log('result', data);
  });
} else {
  const { Poppler } = require('node-poppler');
  const poppler = new Poppler();
  poppler.pdfToPpm(pdf, '/tmp/out', { pngFile: true }).then(console.log);
}
