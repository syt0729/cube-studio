import { TThemeType } from "./theme"

const appLogo = require('./images/AIMTlogo.svg')
const loadingLogo = require('./images/AIMTlogo.svg')

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