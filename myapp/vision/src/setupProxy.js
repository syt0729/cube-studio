// eslint-disable-next-line @typescript-eslint/no-var-requires
const { createProxyMiddleware } = require('http-proxy-middleware');

// https://create-react-app.dev/docs/proxying-api-requests-in-development/
module.exports = function (app) {
    app.use(
        ['**/api/**', '/myapp'],
        createProxyMiddleware({
            //target: 'http://localhost',
            target: 'http://192.168.1.249:80',
            changeOrigin: true,
        })
    );
};