import { TThemeType } from "./theme"

const appLogo = require('./images/Niii.png')
const loadingLogo = require('./images/Niii.png')

interface IGlobalConfig {
    appLogo: any,
    loadingLogo: any,
    theme: TThemeType,
}

const globalConfig: IGlobalConfig = {
    appLogo,
    loadingLogo,
    theme: 'star',
}

export default globalConfig