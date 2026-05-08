const path = require('path');
module.exports = {
  webpack: {
    alias: { '@': path.resolve(__dirname, 'src') },
    configure: (webpackConfig) => {
      webpackConfig.plugins = webpackConfig.plugins.filter(
        (p) => p.constructor.name !== 'ForkTsCheckerWebpackPlugin' && p.constructor.name !== 'ESLintWebpackPlugin'
      );
      return webpackConfig;
    },
  },
};
