/// <reference types="cypress" />
// ***********************************************************
// This example plugins/index.js can be used to load plugins
//
// You can change the location of this file or turn off loading
// the plugins file with the 'pluginsFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/plugins-guide
// ***********************************************************

// This function is called when a project is opened or re-opened (e.g. due to
// the project's config changing)

const {
  addMatchImageSnapshotPlugin,
} = require('cypress-image-snapshot/plugin');

module.exports = (on, config) => {
  on('before:browser:launch', (browser = {}, launchOptions) => {
    if (browser.name == 'chrome') {
      launchOptions.args.push('--disable-gpu')
      launchOptions.args.push('--disable-dev-shm-usage');
      launchOptions.args.push('--js-flags="--max_old_space_size=8192 --max_semi_space_size=8192"');
    }
    return launchOptions
  }),
  addMatchImageSnapshotPlugin(on, config);
};
